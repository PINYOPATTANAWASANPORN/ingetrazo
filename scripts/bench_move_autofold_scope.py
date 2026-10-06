"""Compare full-mesh and incident-face Autofold checks on a real .igz mesh.

Usage: python scripts/bench_move_autofold_scope.py examples/pileta-fuente-yanque.igz
Only the in-memory scene is edited. Timings isolate Autofold, excluding load,
snapshot restore, and the shared-vertex translation common to both paths.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from formats.igz import load_scene
from core.topology import fold_nonplanar_faces


def _groups(groups):
    for group in groups:
        yield group
        yield from _groups(group.children)


def measure(path: Path, repeats: int = 7) -> dict:
    scene = load_scene(path)
    meshes = [scene.mesh, *(group.mesh for group in _groups(scene.groups))]
    candidates = [mesh for mesh in meshes if any(
        len(face.loop) == 4 and not face.holes for face in mesh.faces)]
    if not candidates:
        raise ValueError("document has no quad face for an Autofold move")
    mesh = max(candidates, key=lambda item: len(item.faces))
    face = next(f for f in mesh.faces if len(f.loop) == 4 and not f.holes)
    vertex = face.loop[0]
    delta = face.normal().normalized() * 0.1
    touched = vertex.faces()
    before = mesh.capture_state()
    timings = {"full_ms": [], "local_ms": []}
    expected = None
    try:
        for _ in range(repeats):
            for name, candidates in (("full_ms", None),
                                     ("local_ms", touched)):
                mesh.move_vertex(vertex, delta)
                start = time.perf_counter()
                folded = fold_nonplanar_faces(mesh, faces=candidates)
                timings[name].append((time.perf_counter() - start) * 1000)
                result = (len(folded), len(mesh.faces))
                if expected is None:
                    expected = result
                elif result != expected:
                    raise AssertionError(f"different fold result: {result} != {expected}")
                mesh.restore_state(before)
    finally:
        mesh.restore_state(before)
    return {
        "document": str(path), "mesh_faces": len(mesh.faces),
        "incident_faces": len(touched), "folded_faces": expected[0],
        "repeats": repeats,
        "median_full_ms": round(statistics.median(timings["full_ms"]), 3),
        "median_local_ms": round(statistics.median(timings["local_ms"]), 3),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("document", type=Path)
    parser.add_argument("--repeats", type=int, default=7)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    print(json.dumps(measure(args.document, args.repeats), indent=2))
