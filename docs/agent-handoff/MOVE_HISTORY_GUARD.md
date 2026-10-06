# Move transaction guard and native paint baseline

Base: draft PR #64 (`perf/move-position-snapshot`). Branch:
`perf/move-history-transaction` ([draft PR #65](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/65)).

`MoveVerticesCommand` already captures an identity-preserving pre-edit state for
Undo, but `History.execute` also captured the entire active mesh immediately
before every command. That extra transactional guard was discarded on success.
On a large mesh it cost more than the position-only Move command itself.

For a new, exact `MoveVerticesCommand`, History now uses the command's own
`_before` snapshot to roll back a failed `do`. The command assigns this
snapshot before its first vertex mutation. A preflight failure leaves the
mesh untouched; a failure after movement restores positions and the vertex
registry, or full topology when Autofold was required. Reused Move commands,
subclasses and other commands retain History's full-mesh guard. The failed
command stays off Undo, and History still logs the error and invalidates the
selection. Tests inject failures before mutation, after one moved vertex and
after Autofold modifies topology.

The benchmark scripts load a bundled `.igz` and add an isolated triangle in
memory. The input file is unchanged. Seven interleaved trials of actual
`History.execute`, with and without an additional full `capture_state` to
emulate the old guard, gave these Windows medians:

| Mesh | Old extra guard + Move | New self-guarded Move |
| --- | ---: | ---: |
| `pileta-fuente-yanque.igz`, 7,633 faces | 47.285 ms | 16.852 ms |
| `arco-yanque.igz`, 1,501 faces | 12.274 ms | 4.402 ms |

Run `python scripts/bench_move_history_guard.py
examples/pileta-fuente-yanque.igz` to reproduce the command comparison.
The native Windows GL probe in `scripts/bench_move_paint.py` creates a
standalone 640×480 viewport off screen, avoiding MainWindow settings. Five
interleaved trials on the 7,633-face mesh measured median command time of
45.398 ms with the old extra guard versus 17.540 ms without it. The forced
`paintGL` call still took 816.449 versus 810.135 ms respectively. These are
command plus synchronous paint timings, **not** user-input-to-visible-pixel
latency: they exclude Qt scheduling, buffer swap and display scanout. They
also move a synthetic triangle, so they do not measure the share of real
moves eligible for position-only snapshots.

`INGETRAZO_PERF=1` broke the paint time down into roughly 590 ms for
`_sync_edges` and 210 ms for edge drawing; faces contributed little in this
fixture. Next performance work should target cache invalidation and edge
buffer construction on local Move, with a real GUI interaction check. Do not
claim that this History optimization alone makes the visible drag fast.

The installed `C:\Program Files\IngeTrazo` build remains `3815ef8`; this
branch only changes source and CI coverage.

Validation: the 195-test Windows offscreen CI selection passed. Running the
entire `not slow` suite with Windows offscreen stopped at an unrelated
Composer font-pixel assertion in `test_composer_etiqueta.py` (577 passed,
11 skipped before it); that same test passed with native Windows Qt.
