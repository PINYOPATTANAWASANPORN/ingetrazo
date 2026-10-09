"""Measure native-document Open to the first model frame submitted by Qt.

Run on a visible native desktop. QOpenGLWidget.frameSwapped is a Qt submission
boundary, not a measurement of monitor scanout. The runner opens each corpus
document in a fresh process and never saves it.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.bench_igz_corpus import (DEFAULT_CORPUS, cases_from_manifest,
                                       file_hash)

RESULT_PREFIX = "INGETRAZO_FIRST_FRAME_RESULT:"


def _worker(path: Path, timeout_ms: int, profile_phases: bool = False) -> None:
    if profile_phases:
        # viewport reads this switch at import time. Capture its existing
        # telemetry in memory so a benchmark never writes into the user profile.
        os.environ["INGETRAZO_PERF"] = "1"
        os.environ["INGETRAZO_PERF_ALL_FRAMES"] = "1"
        os.environ.setdefault("INGETRAZO_PERF_LOG", os.devnull)
    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtGui import QSurfaceFormat
    from PySide6.QtWidgets import QApplication

    import views.main_window as main_window
    import views.viewport as viewport_module
    from views.viewport import Viewport

    perf_events: list[tuple[str, float, str]] = []
    if profile_phases:
        def capture(tag: str, ms: float, extra: str = "",
                    floor: float = 50.0) -> None:
            perf_events.append((tag, ms, extra))
        viewport_module._plog = capture

    fmt = QSurfaceFormat()
    fmt.setVersion(3, 3)
    fmt.setProfile(QSurfaceFormat.CoreProfile)
    fmt.setDepthBufferSize(24)
    fmt.setStencilBufferSize(8)
    QSurfaceFormat.setDefaultFormat(fmt)

    app = QApplication([])
    app.setApplicationName("IngeTrazoFirstFrameBenchmark")
    app.setOrganizationName("IngeTrazoBenchmark")

    class TimedViewport(Viewport):
        def paintGL(self) -> None:
            self.bench_paint_start = time.perf_counter()
            self.bench_paint_version = self.scene.version
            perf_start = len(perf_events)
            try:
                super().paintGL()
            finally:
                self.bench_paint_end = time.perf_counter()
                self.bench_paint_events = perf_events[perf_start:]

    main_window.Viewport = TimedViewport
    window = main_window.MainWindow()
    window.resize(960, 640)
    window.show()
    app.processEvents()
    viewport = window.viewport
    if viewport._gl is None:
        raise RuntimeError("native OpenGL context unavailable")

    marks: dict[str, float] = {}
    heartbeat = {"last": 0.0, "max_gap": 0.0, "ticks": 0}
    initial_version = viewport.scene.version
    loop = QEventLoop()
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    tick_timer = QTimer()
    tick_timer.setInterval(50)

    def tick() -> None:
        now = time.perf_counter()
        heartbeat["max_gap"] = max(heartbeat["max_gap"],
                                   now - heartbeat["last"])
        heartbeat["last"] = now
        heartbeat["ticks"] += 1

    tick_timer.timeout.connect(tick)

    def scene_ready(version: int) -> None:
        if version > initial_version and "ready" not in marks:
            marks["ready"] = time.perf_counter()
            marks["load_event_gap"] = max(
                heartbeat["max_gap"], marks["ready"] - heartbeat["last"])
            marks["load_ticks"] = heartbeat["ticks"]

    def swapped() -> None:
        ready = marks.get("ready")
        paint_end = getattr(viewport, "bench_paint_end", 0)
        if (ready is None or paint_end < ready or
                getattr(viewport, "bench_paint_version", None) !=
                viewport.scene.version):
            return
        marks["paint_start"] = viewport.bench_paint_start
        marks["paint_end"] = paint_end
        marks["swap"] = time.perf_counter()
        marks["open_to_swap_event_gap"] = max(
            heartbeat["max_gap"], marks["swap"] - heartbeat["last"])
        loop.quit()

    viewport.sceneVersionChanged.connect(scene_ready)
    viewport.frameSwapped.connect(swapped)
    try:
        marks["open_start"] = time.perf_counter()
        heartbeat["last"] = marks["open_start"]
        tick_timer.start()
        if not window.open_path(path):
            raise RuntimeError("open_path returned false")
        marks["open_return"] = time.perf_counter()
        if "ready" not in marks:
            raise RuntimeError("document-ready signal did not arrive")
        if "swap" not in marks:
            timer.start(timeout_ms)
            loop.exec()
        if "swap" not in marks:
            raise TimeoutError("Qt did not submit a model frame")
        result = {
            "open_to_ready_ms": (marks["ready"] - marks["open_start"]) * 1000,
            "open_to_return_ms": (marks["open_return"] - marks["open_start"]) * 1000,
            "ready_to_paint_ms": (marks["paint_start"] - marks["ready"]) * 1000,
            "paint_ms": (marks["paint_end"] - marks["paint_start"]) * 1000,
            "paint_to_swap_ms": (marks["swap"] - marks["paint_end"]) * 1000,
            "open_to_swap_ms": (marks["swap"] - marks["open_start"]) * 1000,
            "max_load_event_gap_ms": marks["load_event_gap"] * 1000,
            "max_open_to_swap_event_gap_ms":
                marks["open_to_swap_event_gap"] * 1000,
        }
        if any(value < 0 for value in result.values()):
            raise RuntimeError("invalid first-frame timestamp ordering")
        result = {key: round(value, 3) for key, value in result.items()}
        result["heartbeat_ticks_before_ready"] = marks["load_ticks"]
        if profile_phases:
            events = viewport.bench_paint_events
            frames = [event for event in events if event[0] == "frame"]
            if len(frames) != 1:
                raise RuntimeError("matching model paint has no single phase record")
            phases = dict(re.findall(r"(\w+)=(\d+)ms", frames[0][2]))
            for name in ("ground", "sync", "shadowmap", "faces", "edges"):
                if name not in phases:
                    raise RuntimeError(f"missing {name} paint phase")
                result[f"phase_{name}_ms"] = int(phases[name])
            for tag in ("sync_edges", "chunk_rebuild", "chunk_from_disk"):
                durations = [ms for event_tag, ms, _ in events
                             if event_tag == tag]
                result[f"{tag}_total_ms"] = round(sum(durations), 3)
                result[f"{tag}_count"] = len(durations)
            sync = [extra for tag, _, extra in events if tag == "sync_edges"]
            if len(sync) != 1:
                raise RuntimeError("matching paint has no single sync record")
            subphases = dict(re.findall(r"(\w+)=(\d+)ms", sync[0]))
            for name in ("edge_blocks", "selection", "face_blocks",
                         "face_uploads"):
                if name not in subphases:
                    raise RuntimeError(f"missing {name} sync phase")
                result[f"sync_{name}_ms"] = int(subphases[name])
        print(RESULT_PREFIX + json.dumps(result))
    finally:
        timer.stop()
        tick_timer.stop()
        viewport.frameSwapped.disconnect(swapped)
        viewport.sceneVersionChanged.disconnect(scene_ready)
        window.close()


def measure(corpus: Path = DEFAULT_CORPUS, repeats: int = 3,
            timeout: int = 180, profile_phases: bool = False) -> dict:
    if repeats < 1 or timeout < 1:
        raise ValueError("repeats and timeout must be positive")
    cases = cases_from_manifest(corpus)
    report = {
        "schema_version": 1,
        "boundary": "MainWindow.open_path to model frameSwapped on visible native Qt; excludes process startup and monitor scanout",
        "environment": {"os": platform.platform(),
                        "machine": platform.machine(),
                        "python": platform.python_version(),
                        "cpu_count": os.cpu_count()},
        "repeats": repeats,
        "profile_phases": profile_phases,
        "cases": [],
    }
    for case in cases:
        samples = []
        for _ in range(repeats):
            with tempfile.TemporaryDirectory(prefix="ingetrazo-first-frame-") as scratch:
                env = os.environ.copy()
                # Keep QSettings and per-user plugins away from the user's
                # real profile while each full MainWindow is instantiated.
                env["APPDATA"] = scratch
                env["LOCALAPPDATA"] = scratch
                env["XDG_DATA_HOME"] = scratch
                # GenericDataLocation may ignore the temporary profile on
                # some Qt builds. Pin the chunk/texture cache to this sample.
                env["INGETRAZO_TEXTURE_CACHE"] = str(Path(scratch) / "textures")
                env["INGETRAZO_PERF"] = "1" if profile_phases else "0"
                env["INGETRAZO_PERF_ALL_FRAMES"] = "1" if profile_phases else "0"
                env["INGETRAZO_PERF_LOG"] = os.devnull
                command = [sys.executable, str(Path(__file__).resolve()),
                           "--worker", str(case["absolute_path"]),
                           "--timeout", str(timeout)]
                if profile_phases:
                    command.append("--profile-phases")
                process = subprocess.run(
                    command,
                    cwd=ROOT, env=env, capture_output=True, text=True,
                    timeout=timeout + 30, check=False,
                )
            lines = [line[len(RESULT_PREFIX):] for line in process.stdout.splitlines()
                     if line.startswith(RESULT_PREFIX)]
            if process.returncode or len(lines) != 1:
                raise RuntimeError(f"{case['id']} first-frame worker failed "
                                   f"(exit {process.returncode}): "
                                   + process.stderr[-2000:])
            samples.append(json.loads(lines[0]))
        if file_hash(case["absolute_path"]) != case["sha256"]:
            raise RuntimeError(f"{case['id']} source document changed")
        report["cases"].append({
            "id": case["id"], "path": case["path"],
            "sha256": case["sha256"], "samples_ms": samples,
            "median_ms": {key: round(statistics.median(s[key] for s in samples), 3)
                          for key in samples[0]},
        })
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--profile-phases", action="store_true",
                        help="capture first model paint phases and chunk build timing")
    parser.add_argument("--worker", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker is not None:
        _worker(args.worker, args.timeout * 1000, args.profile_phases)
    else:
        result = measure(args.corpus, args.repeats, args.timeout,
                         args.profile_phases)
        output = json.dumps(result, indent=2) + "\n"
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(output, encoding="utf-8")
        print(output)
