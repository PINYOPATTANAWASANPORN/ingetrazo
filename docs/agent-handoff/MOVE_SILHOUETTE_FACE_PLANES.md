# Batch Face planes for loose soft-edge silhouettes

Base: draft PR #72 (`perf/move-face-bucket-key`). Branch:
`perf/move-silhouette-face-plane` ([draft PR #73](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/73)).

After a local Move, silhouette preparation read the first three vertices of
each incident Face for every soft edge, and assigned both triangle arrays
one edge at a time. Adjacent edges commonly share a Face. The renderer now
captures each Face plane once per rebuild, records the two Face indices for
each edge, and gathers the triangle arrays in NumPy. All snapshots are local
to the call, so a later Move, Undo or Redo cannot reuse stale coordinates.
The existing single-face and non-manifold rule still uses the first Face for
both sides; exactly two incident Faces use the first two.

On the bundled `examples/pileta-fuente-yanque.igz` mesh with 15,312 soft
edges, an alternating same-process comparison measured 74.9 ms before and
48.2 ms after for `_loose_soft_edge_arrays` (nine warmed samples per mode).
Native Windows 640x480 direct `paintGL` after a planar Move on that mesh plus
a detached triangle measured 145.8 ms before versus 123.6 ms after (also
nine warmed samples per mode). The exact six returned NumPy arrays matched
the previous implementation on the model. These probes exclude Qt event
scheduling, buffer swap, display scanout and input-to-visible-pixel latency.

The focused geometry, Tag, Hide, material, texture and render suite passed
105 tests with three platform skips. Added tests check shared-Face reads
within one rebuild, fresh coordinates on the next rebuild, and empty arrays.
Existing tests cover one-, two- and many-Face planes. `compileall` and
`git diff --check` passed. Hosted CI for code commit
`3ba6d9c241ed2d615ded38354036853de740c18b` is run
[37662372329](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/actions/runs/37662372329),
which passed Ubuntu `pytest (not slow)` and Windows Qt offscreen smoke.

Next: measure Move from a real GUI pointer event to visible pixels, then
profile the remaining Face signature and bucketing work on representative
models. The installed `C:\Program Files\IngeTrazo` build remains at `3815ef8`.
