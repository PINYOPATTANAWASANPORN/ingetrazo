"""Measure in-memory Move command latency on a bundled .igz mesh.

Usage: python scripts/bench_move_command.py examples/pileta-fuente-yanque.igz
This excludes document loading, viewport redraw, and file I/O. It does not
write the document. Each measured Move uses a fresh command and is undone.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.history import MoveVerticesCommand
from core.scene import Scene
from formats.igz import load_scene


def _groups(groups):
    for group in groups:
        yield group
        yield from _groups(group.children)


def measure(path: Path, repeats: int = 7) -> dict:
    loaded = load_scene(path)
    meshes = [loaded.mesh, *(group.mesh for group in _groups(loaded.groups))]
    candidates = [mesh for mesh in meshes if any(
        len(face.loop) == 4 and not face.holes for face in mesh.faces)]
    if not candidates:
        raise ValueError("document has no quad face for a Move benchmark")
    mesh = max(candidates, key=lambda item: len(item.faces))
    face = next(f for f in mesh.faces if len(f.loop) == 4 and not f.holes)
    vertex = face.loop[0]
    original_position = type(vertex.position)(vertex.position)
    face_count = len(mesh.faces)
    delta = face.normal().normalized() * 0.1
    scene = Scene(mesh=mesh)
    timings = {"snapshot_ms": [], "move_ms": [], "undo_ms": []}

    for _ in range(repeats):
        start = time.perf_counter()
        mesh.capture_state()
        timings["snapshot_ms"].append((time.perf_counter() - start) * 1000)

        command = MoveVerticesCommand([original_position], delta)
        start = time.perf_counter()
        command.do(scene)
        timings["move_ms"].append((time.perf_counter() - start) * 1000)
        start = time.perf_counter()
        command.undo(scene)
        timings["undo_ms"].append((time.perf_counter() - start) * 1000)
        if vertex.position != original_position or len(mesh.faces) != face_count:
            raise AssertionError("Move undo did not restore the sampled mesh")

    return {
        "document": str(path), "mesh_faces": face_count,
        "repeats": repeats,
        **{f"median_{name}": round(statistics.median(values), 3)
           for name, values in timings.items()},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("document", type=Path)
    parser.add_argument("--repeats", type=int, default=7)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    print(json.dumps(measure(args.document, args.repeats), indent=2))
