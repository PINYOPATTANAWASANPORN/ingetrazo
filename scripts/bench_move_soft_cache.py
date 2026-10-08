"""Compare queued Move frames with and without loose silhouette reuse.

Run on a visible native desktop::

    python scripts/bench_move_soft_cache.py examples/pileta-fuente-yanque.igz

The baseline disables only the new preservation marker. Both modes use the
same renderer, model, Qt frame boundary and Move/Undo validation. The result
ends at QOpenGLWidget.frameSwapped, not monitor scanout.
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


def compare(path: Path, repeats: int = 5, rounds: int = 2) -> dict:
    original_mark = MoveVerticesCommand._mark_soft_arrays
    original_arrays = viewport_module._loose_soft_edge_arrays
    counts = {"without_reuse": 0, "with_reuse": 0}
    samples = {name: [] for name in counts}
    active = "without_reuse"

    def count_arrays(softs):
        counts[active] += 1
        return original_arrays(softs)

    def disable_reuse(self, scene, old_version, old_serial):
        scene._soft_edge_arrays_preserved = None

    viewport_module._loose_soft_edge_arrays = count_arrays
    try:
        for cycle in range(rounds):
            order = (("without_reuse", "with_reuse") if cycle % 2 == 0
                     else ("with_reuse", "without_reuse"))
            for active in order:
                MoveVerticesCommand._mark_soft_arrays = (
                    disable_reuse if active == "without_reuse"
                    else original_mark)
                before = counts[active]
                result = measure(path, repeats=repeats)
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
        "boundary": "queued Move to Qt frameSwapped; excludes monitor scanout",
        "repeats_per_run": repeats,
        "rounds": rounds,
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
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--rounds", type=int, default=2)
    args = parser.parse_args()
    if args.repeats < 1 or args.rounds < 1:
        parser.error("--repeats and --rounds must be positive")
    print(json.dumps(compare(args.document, args.repeats, args.rounds),
                     indent=2))
