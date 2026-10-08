"""Compare coalesced safe Moves with and without silhouette-cache chaining.

Run on a visible native desktop::

    python scripts/bench_move_soft_chain.py examples/pileta-fuente-yanque.igz

The baseline uses PR #77's single-transition marker. Each queued action
performs several safe Moves before Qt paints one frame. Times end at
QOpenGLWidget.frameSwapped, not physical display scanout.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.history import MoveVerticesCommand
from scripts.bench_move_qt_frame import measure
import views.viewport as viewport_module


def compare(path: Path, repeats: int = 3, rounds: int = 2,
            steps_per_frame: int = 3) -> dict:
    original_mark = MoveVerticesCommand._mark_soft_arrays
    original_arrays = viewport_module._loose_soft_edge_arrays
    counts = {"single_transition": 0, "chained": 0}
    samples = {name: [] for name in counts}
    active = "single_transition"

    def count_arrays(softs):
        counts[active] += 1
        return original_arrays(softs)

    def single_transition(self, scene, old_version, old_serial):
        scene._soft_edge_arrays_preserved = (
            (old_version, old_serial, scene.version, scene.mesh._mut_serial)
            if self._soft_arrays_unchanged else None)

    viewport_module._loose_soft_edge_arrays = count_arrays
    try:
        for cycle in range(rounds):
            order = (("single_transition", "chained") if cycle % 2 == 0
                     else ("chained", "single_transition"))
            for active in order:
                MoveVerticesCommand._mark_soft_arrays = (
                    single_transition if active == "single_transition"
                    else original_mark)
                before = counts[active]
                result = measure(path, repeats=repeats,
                                 steps_per_frame=steps_per_frame)
                samples[active].append({
                    "paint_ms": result["median_ms"]["paint_ms"],
                    "total_ms": result["median_ms"]["total_ms"],
                    "array_builds": counts[active] - before,
                })
    finally:
        MoveVerticesCommand._mark_soft_arrays = original_mark
        viewport_module._loose_soft_edge_arrays = original_arrays
    return {
        "document": str(path),
        "boundary": "queued coalesced Moves to Qt frameSwapped",
        "repeats_per_run": repeats,
        "rounds": rounds,
        "steps_per_frame": steps_per_frame,
        "runs": samples,
        "median_of_run_medians_ms": {
            mode: {name: round(statistics.median(s[name] for s in values), 3)
                   for name in ("paint_ms", "total_ms")}
            for mode, values in samples.items()
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("document", type=Path)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--rounds", type=int, default=2)
    parser.add_argument("--steps-per-frame", type=int, default=3)
    args = parser.parse_args()
    if min(args.repeats, args.rounds, args.steps_per_frame) < 1:
        parser.error("--repeats, --rounds and --steps-per-frame must be positive")
    print(json.dumps(compare(args.document, args.repeats, args.rounds,
                             args.steps_per_frame), indent=2))
