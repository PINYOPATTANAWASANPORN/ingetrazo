"""Benchmark Move command and a forced OpenGL paint on a real example mesh.

Run from a Windows desktop session, for example::

    python scripts/bench_move_paint.py examples/pileta-fuente-yanque.igz

The model is loaded in memory and an isolated triangle is added outside its
bounds so Move stays planar. A standalone viewport is shown outside the screen
to obtain a native GL context without touching MainWindow settings. Timings
exclude file loading and input dispatch; paint is a direct paintGL call and
does not include Qt scheduling, buffer swap, or display scanout.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

from PySide6.QtGui import QVector3D
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.history import History, MoveVerticesCommand
from core.scene import Scene
from formats.igz import load_scene
from views.viewport import Viewport


def _groups(groups):
    for group in groups:
        yield group
        yield from _groups(group.children)


def measure(path: Path, repeats: int = 7) -> dict:
    app = QApplication.instance() or QApplication([])
    loaded = load_scene(path)
    mesh = max((loaded.mesh, *(g.mesh for g in _groups(loaded.groups))),
               key=lambda item: len(item.faces))
    scene = Scene(mesh=mesh)
    bounds = scene.bounds()
    x = max((v.position.x() for v in mesh.vertices), default=0) + 1000
    source = QVector3D(x, 0, 0)
    mesh.add_face([source, QVector3D(x + 2, 0, 0), QVector3D(x, 2, 0)])
    vertex = mesh.vertex_at(source)
    history = History(scene)
    viewport = Viewport()
    try:
        viewport.resize(640, 480)
        viewport.move(-2000, -2000)
        viewport.show()
        app.processEvents()
        if viewport._gl is None:
            raise RuntimeError("native OpenGL context unavailable")
        viewport.set_document(scene, history)
        if bounds[0] is not None:
            viewport.camera.fit_to(*bounds)

        def paint() -> float:
            start = time.perf_counter()
            viewport.makeCurrent()
            try:
                viewport.paintGL()
            finally:
                viewport.doneCurrent()
            return (time.perf_counter() - start) * 1000

        paint()  # compile shaders and populate the first-frame caches
        delta = QVector3D(0, 0, 0.1)
        modes = ("with_extra_full_guard", "self_guarded")
        times = {mode: {"command_ms": [], "paint_ms": [], "total_ms": []}
                 for mode in modes}
        for _ in range(repeats):
            for mode in modes:
                command = MoveVerticesCommand([source], delta)
                start = time.perf_counter()
                if mode == "with_extra_full_guard":
                    mesh.capture_state()  # old History.execute guard
                history.execute(command)
                command_done = time.perf_counter()
                paint_ms = paint()
                times[mode]["command_ms"].append(
                    (command_done - start) * 1000)
                times[mode]["paint_ms"].append(paint_ms)
                times[mode]["total_ms"].append(
                    (command_done - start) * 1000 + paint_ms)
                if history.last_error or not command._position_only:
                    raise AssertionError("unexpected Move failure or Autofold")
                history.undo()
                paint()  # reset paint caches before the next trial
                history.clear()
                if vertex.position != source or mesh.vertex_at(source) is not vertex:
                    raise AssertionError("Undo failed to restore the sampled vertex")
        return {
            "document": str(path),
            "mesh_faces_with_synthetic_triangle": len(mesh.faces),
            "repeats": repeats,
            "viewport": "640x480 native Windows OpenGL; direct paintGL",
            "median_ms": {
                mode: {key: round(statistics.median(values), 3)
                       for key, values in result.items()}
                for mode, result in times.items()
            },
        }
    finally:
        viewport.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("document", type=Path)
    parser.add_argument("--repeats", type=int, default=7)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    print(json.dumps(measure(args.document, args.repeats), indent=2))
