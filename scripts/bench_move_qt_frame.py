"""Measure Move command to Qt frame submission on a native desktop.

Run with ``python scripts/bench_move_qt_frame.py examples/pileta-fuente-yanque.igz``.
Unlike ``bench_move_paint.py``, this leaves painting to Qt and waits for
``QOpenGLWidget.frameSwapped``. The temporary window must be visible; moving
it outside the screen suppresses the signal on Windows. This measures a
queued command, repaint, and Qt composition. It does not measure Move tool
picking, physical mouse delivery, monitor scanout, or display latency.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtGui import QVector3D
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.history import History, MoveVerticesCommand
from core.scene import Scene
from formats.igz import load_scene
from views.viewport import Viewport


class TimedViewport(Viewport):
    def paintGL(self) -> None:
        self.paint_start = time.perf_counter()
        try:
            super().paintGL()
        finally:
            self.paint_end = time.perf_counter()


def _groups(groups):
    for group in groups:
        yield group
        yield from _groups(group.children)


def measure(path: Path, repeats: int = 7, timeout_ms: int = 10000,
            steps_per_frame: int = 1) -> dict:
    if steps_per_frame < 1:
        raise ValueError("steps_per_frame must be positive")
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
    viewport = TimedViewport()
    try:
        viewport.resize(640, 480)
        viewport.show()
        app.processEvents()
        if viewport._gl is None:
            raise RuntimeError("native OpenGL context unavailable")
        viewport.set_document(scene, history)
        if bounds[0] is not None:
            viewport.camera.fit_to(*bounds)

        def frame(action):
            sample = {}
            loop = QEventLoop()
            timer = QTimer()
            timer.setSingleShot(True)
            timer.timeout.connect(loop.quit)

            def apply():
                sample["handler_start"] = time.perf_counter()
                action()
                sample["handler_end"] = time.perf_counter()
                viewport.update()

            def swapped():
                paint_end = getattr(viewport, "paint_end", 0)
                if paint_end <= sample.get("handler_end", float("inf")):
                    return  # a frame already queued before this command
                sample["swap"] = time.perf_counter()
                sample["paint_start"] = viewport.paint_start
                sample["paint_end"] = paint_end
                loop.quit()

            viewport.frameSwapped.connect(swapped)
            try:
                sample["queued"] = time.perf_counter()
                QTimer.singleShot(0, apply)
                timer.start(timeout_ms)
                loop.exec()
            finally:
                timer.stop()
                viewport.frameSwapped.disconnect(swapped)
            if "swap" not in sample:
                raise TimeoutError("Qt did not submit a frame after Move")
            return {
                "queue_ms": (sample["handler_start"] - sample["queued"]) * 1000,
                "command_ms": (sample["handler_end"] - sample["handler_start"]) * 1000,
                "schedule_ms": (sample["paint_start"] - sample["handler_end"]) * 1000,
                "paint_ms": (sample["paint_end"] - sample["paint_start"]) * 1000,
                "composition_ms": (sample["swap"] - sample["paint_end"]) * 1000,
                "total_ms": (sample["swap"] - sample["queued"]) * 1000,
            }

        frame(lambda: None)  # compile shaders and populate the first-frame caches
        samples = []
        delta = QVector3D(0, 0, 0.1)
        for _ in range(repeats):
            commands = []

            def move_steps():
                for _ in range(steps_per_frame):
                    command = MoveVerticesCommand([QVector3D(vertex.position)],
                                                  delta)
                    history.execute(command)
                    commands.append(command)

            samples.append(frame(move_steps))
            if history.last_error or not all(c._position_only for c in commands):
                raise AssertionError("unexpected Move failure or Autofold")
            frame(lambda: [history.undo() for _ in commands])
            history.clear()
            if vertex.position != source or mesh.vertex_at(source) is not vertex:
                raise AssertionError("Undo failed to restore the sampled vertex")
        return {
            "document": str(path),
            "mesh_faces_with_synthetic_triangle": len(mesh.faces),
            "repeats": repeats,
            "steps_per_frame": steps_per_frame,
            "viewport": "640x480 visible native Qt OpenGL",
            "boundary": "queued Move command to QOpenGLWidget.frameSwapped",
            "median_ms": {key: round(statistics.median(s[key] for s in samples), 3)
                          for key in samples[0]},
            "samples_ms": [{key: round(value, 3) for key, value in sample.items()}
                           for sample in samples],
        }
    finally:
        viewport.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("document", type=Path)
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--timeout-ms", type=int, default=10000)
    parser.add_argument("--steps-per-frame", type=int, default=1)
    args = parser.parse_args()
    if args.repeats < 1 or args.timeout_ms < 1 or args.steps_per_frame < 1:
        parser.error("--repeats, --timeout-ms and --steps-per-frame must be positive")
    print(json.dumps(measure(args.document, args.repeats, args.timeout_ms,
                             args.steps_per_frame), indent=2))
