"""Measure IGZ decode/hydration on a hash-pinned real-model corpus.

Each sample loads in a fresh Python process. Timing starts immediately before
``load_scene`` and excludes interpreter startup, GUI construction and painting.
The runner never writes the source documents.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS = ROOT / "benchmarks" / "models" / "corpus-v1.json"
RESULT_PREFIX = "INGETRAZO_BENCH_RESULT:"


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def cases_from_manifest(manifest: Path, root: Path = ROOT) -> list[dict]:
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or not isinstance(data.get("cases"), list):
        raise ValueError("unsupported model corpus schema")
    if not data["cases"]:
        raise ValueError("model corpus is empty")
    seen = set()
    cases = []
    root = root.resolve()
    for case in data["cases"]:
        if not isinstance(case, dict):
            raise ValueError("invalid corpus case")
        name, relative, expected = (case.get(key) for key in
                                    ("id", "path", "sha256"))
        if not isinstance(name, str) or not name or name in seen:
            raise ValueError("missing or duplicate case id")
        if not isinstance(relative, str) or not relative.endswith(".igz"):
            raise ValueError(f"invalid IGZ path for {name}")
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError(f"corpus file missing or outside checkout: {relative}")
        if not isinstance(expected, str) or len(expected) != 64:
            raise ValueError(f"invalid SHA-256 for {name}")
        actual = file_hash(path)
        if actual != expected.lower():
            raise ValueError(f"corpus SHA-256 mismatch: {relative}")
        seen.add(name)
        cases.append({"id": name, "path": relative, "absolute_path": path,
                      "sha256": actual, "bytes": path.stat().st_size})
    return cases


def _model_stats(scene) -> dict:
    groups = list(scene.groups)
    all_groups = []
    while groups:
        group = groups.pop()
        all_groups.append(group)
        groups.extend(group.children)
    meshes = [scene.mesh] + [g.mesh for g in all_groups]
    unique = {id(mesh): mesh for mesh in meshes}
    return {
        "top_groups": len(scene.groups),
        "nested_groups": len(all_groups) - len(scene.groups),
        "instances": sum(g.is_instance() for g in all_groups),
        "unique_meshes": len(unique),
        "expanded_faces": sum(len(mesh.faces) for mesh in meshes),
        "unique_faces": sum(len(mesh.faces) for mesh in unique.values()),
        "loose_edges": sum(sum(not edge.faces for edge in mesh.edges)
                           for mesh in unique.values()),
        "soft_edges": sum(sum(edge.soft for edge in mesh.edges)
                          for mesh in unique.values()),
        "textured_faces": sum(sum(bool(face.attrs.get("texture"))
                                  for face in mesh.faces)
                              for mesh in unique.values()),
    }


def _worker(path: Path) -> None:
    sys.path.insert(0, str(ROOT))
    from formats.igz import load_scene

    start = time.perf_counter()
    scene = load_scene(path)
    load_ms = (time.perf_counter() - start) * 1000
    result = {"load_ms": round(load_ms, 3), "stats": _model_stats(scene)}
    print(RESULT_PREFIX + json.dumps(result, separators=(",", ":")))


def run(corpus: Path, repeats: int, timeout: int = 120,
        root: Path = ROOT) -> dict:
    if repeats < 1 or timeout < 1:
        raise ValueError("repeats and timeout must be positive")
    cases = cases_from_manifest(corpus, root)
    result = {
        "schema_version": 1,
        "boundary": "formats.igz.load_scene decode/hydration only; excludes imports, GUI, first paint and interactivity",
        "corpus": str(corpus.resolve()),
        "environment": {"os": platform.platform(),
                        "machine": platform.machine(),
                        "processor": platform.processor(),
                        "python": platform.python_version(),
                        "cpu_count": os.cpu_count()},
        "repeats": repeats,
        "cases": [],
    }
    for case in cases:
        samples = []
        process_samples = []
        stats = None
        for _ in range(repeats):
            process_start = time.perf_counter()
            process = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), "--worker",
                 str(case["absolute_path"])],
                cwd=str(root), capture_output=True, text=True, timeout=timeout,
                check=False,
            )
            process_samples.append(round((time.perf_counter() - process_start) * 1000, 3))
            lines = [line[len(RESULT_PREFIX):] for line in process.stdout.splitlines()
                     if line.startswith(RESULT_PREFIX)]
            if process.returncode or len(lines) != 1:
                raise RuntimeError(f"{case['id']} worker failed (exit {process.returncode}): "
                                   + process.stderr[-2000:])
            sample = json.loads(lines[0])
            if stats is not None and sample["stats"] != stats:
                raise RuntimeError(f"{case['id']} model statistics changed between runs")
            stats = sample["stats"]
            samples.append(sample["load_ms"])
        if file_hash(case["absolute_path"]) != case["sha256"]:
            raise RuntimeError(f"{case['id']} source document changed")
        result["cases"].append({
            "id": case["id"], "path": case["path"],
            "sha256": case["sha256"], "bytes": case["bytes"],
            "stats": stats, "load_ms": samples,
            "median_load_ms": round(statistics.median(samples), 3),
            "min_load_ms": min(samples), "max_load_ms": max(samples),
            "process_wall_ms": process_samples,
            "median_process_wall_ms": round(statistics.median(process_samples), 3),
        })
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--worker", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker is not None:
        _worker(args.worker)
    else:
        result = run(args.corpus, args.repeats, args.timeout)
        output = json.dumps(result, indent=2) + "\n"
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(output, encoding="utf-8")
        print(output)
