"""Measure History.execute's redundant Move guard snapshot on a large mesh.

Usage: python scripts/bench_move_history_guard.py examples/pileta-fuente-yanque.igz

The comparison adds one full `capture_state` immediately before the current
History.execute to emulate its old transactional guard. Both paths execute
the same current Move command and Undo. A detached triangle is added to the
loaded mesh in memory so the edit is planar; the input file is not changed.
Loading, viewport painting and user input are excluded.
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

from core.history import History, MoveVerticesCommand
from core.scene import Scene
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
    history = History(scene)
    delta = QVector3D(0, 0, 0.1)
    times = {"with_extra_full_guard_ms": [], "self_guarded_ms": []}
    for _ in range(repeats):
        for mode, key in ((True, "with_extra_full_guard_ms"),
                          (False, "self_guarded_ms")):
            command = MoveVerticesCommand([source], delta)
            start = time.perf_counter()
            if mode:
                mesh.capture_state()  # old History guard; dropped on success
            history.execute(command)
            times[key].append((time.perf_counter() - start) * 1000)
            if history.last_error or not command._position_only:
                raise AssertionError("unexpected Move failure or Autofold")
            history.undo()
            history.clear()
            if vertex.position != source or mesh.vertex_at(source) is not vertex:
                raise AssertionError("Undo failed to restore the sampled vertex")
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
