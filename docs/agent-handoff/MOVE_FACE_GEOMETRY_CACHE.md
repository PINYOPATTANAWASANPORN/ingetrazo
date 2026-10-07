# Reuse unchanged face geometry after a local Move

Base: draft PR #65 (`perf/move-history-transaction`). Branch:
`perf/move-face-geometry-cache` ([draft PR #66](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/66)).

After Move, the scene version changes and the viewport used to discard all
per-version Newell and triangulation results. The next paint then recalculated
geometry for every loose face, even though a local Move changes only incident
faces. An active mesh `Face` now retains its raw Newell vector and triangle
list across scene versions. The cache key contains the ordered coordinates of
the outer loop and every hole loop. A changed position, winding or hole
invalidates the entry; paint, tag and visibility are still evaluated by the
existing VBO bucketing path. Per-version viewport memos remain in place to
avoid repeated key checks within one paint.

The persistent cache applies only to faces in the active edit mesh when that
mesh has at most 20,000 faces. Group/reference geometry retains its existing
chunk cache, while larger active meshes use only the per-version memo to bound
retained triangle data. A document switch clears viewport references to old
faces. The face-owned entry itself is released when its face is discarded.

Validation on Windows with `QT_QPA_PLATFORM=offscreen` and `PYTHONUTF8=1`:
the 201-test CI selection passed. Focused tests cover unchanged-face reuse,
changed vertex/loop/hole invalidation, Move/Undo/Redo, cache size cap and
document switch. `compileall` and `git diff --check` passed. Hosted
[CI run 37544278293](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/actions/runs/37544278293)
on `f65795d` also passed Windows Qt offscreen smoke and Ubuntu `not slow`.

Native Windows `scripts/bench_move_paint.py` on the bundled
`pileta-fuente-yanque.igz` plus one detached triangle measured median direct
`paintGL` near 584-629 ms over separate five-trial runs, compared with about
810 ms on the parent implementation. This probe uses a standalone 640x480
viewport and forced synchronous paint; it is not user-input-to-visible-pixel
latency. Variation between runs is material, so treat the result as a direction
for further profiling, not a precise speedup claim. The command stayed near
17 ms. Edge bucketing and drawing remain the largest work in this fixture;
the next slice should measure and reduce that cost without stale buffers.

The installed `C:\Program Files\IngeTrazo` build remains `3815ef8`; this
branch only changes source and CI coverage.
