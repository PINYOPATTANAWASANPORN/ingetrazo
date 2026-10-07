# Move latency through Qt frame submission

Base: draft PR #73 (`perf/move-silhouette-face-plane`). Branch:
`perf/move-qt-frame-benchmark` ([draft PR #74](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/74)).

The earlier Move paint benchmark called `paintGL` directly. It was useful for
renderer comparisons but omitted event-loop scheduling and Qt composition.
`scripts/bench_move_qt_frame.py` now opens a visible, native 640x480 viewport,
queues a planar `MoveVerticesCommand` on a detached triangle in the bundled
Yanque example, and waits for `QOpenGLWidget.frameSwapped`. Every trial then
undoes the Move and checks the original vertex identity. This distinguishes
queue wait, command execution, scheduling after the command, paint, and
paint-end to Qt frame submission. It does **not** include physical mouse
delivery, Move-tool picking/hover, or monitor scanout. An off-screen-positioned
window cannot be used for this signal on native Windows; it did not emit
`frameSwapped` in the local check.

Run from a visible Windows desktop session:

```powershell
python scripts/bench_move_qt_frame.py examples/pileta-fuente-yanque.igz --repeats 7
```

The native Windows run on the 7,633-face mesh (including the detached triangle)
reported medians of 0.062 ms queue, 17.471 ms command, 0.223 ms scheduling,
135.435 ms paint, 3.860 ms composition and 157.547 ms total. These are one
machine's seven samples, not a release performance guarantee. `INGETRAZO_PERF=1`
now also logs `frame.submitted` for real pointer-driven paints and includes
`paint_to_swap` in that line. The existing `frame` log remains a paint-side
breakdown. The live log uses the latest pointer event before a paint, so it
should not be interpreted as earliest-event latency when events coalesce.

Native targeted validation: 25 Move/viewport tests passed; `compileall` and
`git diff --check` passed. The benchmark completed seven Move/Undo cycles and
checked that Undo restored the same vertex object.
Hosted CI for code commit `174f957000928dcc97c4e1a85e056e1be7e0fe80` is
[run 37700724495](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/actions/runs/37700724495),
which passed Ubuntu `pytest (not slow)` and Windows Qt offscreen smoke.

The current measurement points to `_sync_edges` and silhouette/edge work
inside paint, not Qt queue wait or composition, as the next profiler target.
A controlled real-pointer
interaction and a monitor-side measurement are still needed before claiming
input-to-visible-pixel latency. The installed `C:\Program Files\IngeTrazo`
build remains at `3815ef8`.
