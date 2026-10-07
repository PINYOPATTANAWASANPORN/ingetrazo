# Share the active-face geometry key during Move paints

Base: draft PR #71 (`perf/move-silhouette-rebuild`). Branch:
`perf/move-face-bucket-key` ([draft PR #72](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/72)).

For each visible untextured Face with a default back, `_sync_edges` packs
triangles into both the default-back and front-colour buffers. Both packing
methods checked the active-mesh retention policy and geometry signature.
The renderer now computes that key once in `bucket_face` and passes it to
both packers. Standalone calls still compute their own key; textured or
non-default-back paths keep their previous behavior. Face-owned caches still
check geometry and front paint, and mesh/document switches still release
entries under the existing limit.

On the bundled `examples/pileta-fuente-yanque.igz` active mesh (7,632 faces),
an alternating same-process microbenchmark of packed front and default-back
lookups measured 60.8 ms with separate keys and 49.2 ms with a shared key
(medians of 20 warmed trials each). The native Windows 640x480 direct
`paintGL` benchmark after a planar Move on that mesh plus a detached triangle
measured 153.0 ms (median of seven trials). The full-frame figure has no
paired baseline in the same run. Both probes exclude Qt scheduling, buffer
swap, display scanout, and actual input-to-visible-pixel latency.

The focused face/material/texture/render suite passed 101 tests with three
platform skips. A new test confirms a single key lookup reaches both
packed buffers after a scene-version bump. Existing tests cover changed
geometry, paint, Move/Undo/Redo and retention caps. An initial broad Windows
run failed because its default cp874 codec cannot read UTF-8 `AUTHORS`;
the UTF-8 retry was stopped early while CI ran. Hosted CI for code commit
`f3cd4474eb25a70a610b29c50505f4adcd6bbc6c` is run
[37655909003](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/actions/runs/37655909003),
which passed Ubuntu `pytest (not slow)` and Windows Qt offscreen smoke.

Next: measure Move input-to-visible-pixel in a real GUI session and profile
the remaining Face-bucketing and GL upload work before another optimization.
The installed `C:\Program Files\IngeTrazo` build remains at `3815ef8`.
