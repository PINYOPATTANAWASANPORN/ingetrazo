# Reduce face geometry signature scans after Move

Base: draft PR #69 (`perf/move-face-visibility-back-buffer`). Branch:
`perf/move-face-signature-tuples` ([draft PR #70](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/70)).

The renderer's persistent Face caches must compare the complete outer and
hole-loop coordinates on each content revision. Direct position mutation is
also used outside `Mesh.move_vertex`, so a mesh mutation counter alone cannot
safely skip this check. `QVector3D.toTuple()` obtains the three components in
one Qt/Python call instead of calling `x()`, `y()` and `z()` separately. It
preserves the same nested tuple key, with no rounding or object-identity
shortcut. A regression test changes both an outer and hole vertex in place.

On the bundled `pileta-fuente-yanque.igz` example's 7,632-face mesh, a full
signature scan measured 23.2 ms with the scalar getters versus 15.4 ms with
`toTuple()`, medians of seven repetitions in one process. A shared-vertex
dictionary variant was slower (26.2 ms) and was not adopted. A separate
native Windows 640x480 direct `paintGL` probe after Move measured 271.6 ms
old versus 264.6 ms new across 12 alternating pairs. Individual frame times
varied considerably; treat the isolated scan as the stronger evidence. The
paint probe excludes input dispatch, Qt scheduling, buffer swap and scanout.

Relevant face, Hide, material, texture and render tests passed 100, with
three platform skips. `compileall` and `git diff --check` passed. Hosted CI
run [37648590045](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/actions/runs/37648590045)
passed Ubuntu `pytest (not slow)` and Windows Qt offscreen smoke on code
commit `e979740714e22ddd596bb841af4bc881b2401bd3`.

A `cProfile` pass of the same post-Move paint attributed 0.479 of 0.735
profiled seconds to `_upload_silhouette_edges`, with 15,312 calls to
`Scene.entity_visible()` under that pass. Profiler overhead makes these
numbers unsuitable as wall-clock timings, but they identify silhouette cache
rebuild and per-edge visibility as the next measured target. Preserve custom
scene visibility and soft-edge silhouette behavior when batching it. Also
measure actual input-to-visible-pixel latency on a representative model. The
installed `C:\Program Files\IngeTrazo` build remains at `3815ef8`.
