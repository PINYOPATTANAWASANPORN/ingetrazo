"""Compare full and position-only Move snapshots on a large loaded mesh.

Usage: python scripts/bench_move_position_snapshot.py examples/pileta-fuente-yanque.igz

Adds one isolated triangle to the largest mesh *in memory* and moves one of
its corners. This keeps the move topologically plain while the unrelated
real-example mesh exercises the old whole-mesh snapshot cost. The file is
never changed. Loading, setup, and viewport painting are excluded.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

from PySide6.QtGui import QVector3D

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.history import MoveVerticesCommand, translate_points
from core.scene import Scene
from core.topology import _key, fold_nonplanar_faces
from formats.igz import load_scene


def _groups(groups):
    for group in groups:
        yield group
        yield from _groups(group.children)


def measure(path: Path, repeats: int = 7) -> dict:
    loaded = load_scene(path)
    mesh = max((loaded.mesh, *(g.mesh for g in _groups(loaded.groups))),
               key=lambda item: len(item.faces))
    x = max((v.position.x() for v in mesh.vertices), default=0) + 1000
    source = QVector3D(x, 0, 0)
    mesh.add_face([source, QVector3D(x + 2, 0, 0), QVector3D(x, 2, 0)])
    vertex = mesh.vertex_at(source)
    scene = Scene(mesh=mesh)
    delta = QVector3D(0, 0, 0.1)
    times = {"full_do_ms": [], "full_undo_ms": [],
             "position_do_ms": [], "position_undo_ms": []}
    for _ in range(repeats):
        for mode in ("full", "position"):
            if mode == "full":
                start = time.perf_counter()
                before = mesh.capture_state()
                touched = translate_points(scene, {_key(source)}, delta,
                                           collect_faces=True)
                fold_nonplanar_faces(mesh, faces=touched)
                mesh.capture_state()  # the old command also saves redo state
                times["full_do_ms"].append((time.perf_counter() - start) * 1000)
                start = time.perf_counter()
                mesh.restore_state(before)
                times["full_undo_ms"].append((time.perf_counter() - start) * 1000)
            else:
                command = MoveVerticesCommand([source], delta)
                start = time.perf_counter()
                command.do(scene)
                times["position_do_ms"].append((time.perf_counter() - start) * 1000)
                if not command._position_only:
                    raise AssertionError("isolated triangle unexpectedly folded")
                start = time.perf_counter()
                command.undo(scene)
                times["position_undo_ms"].append((time.perf_counter() - start) * 1000)
            if vertex.position != source or mesh.vertex_at(source) is not vertex:
                raise AssertionError("Move undo changed the source vertex")
    return {
        "document": str(path), "mesh_faces_with_synthetic_triangle": len(mesh.faces),
        "repeats": repeats,
        **{f"median_{name}": round(statistics.median(values), 3)
           for name, values in times.items()},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("document", type=Path)
    parser.add_argument("--repeats", type=int, default=7)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    print(json.dumps(measure(args.document, args.repeats), indent=2))
