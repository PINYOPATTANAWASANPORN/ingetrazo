# Reuse packed face colour after unrelated edits

Base: draft PR #67 (`perf/move-loose-edge-render`). Branch:
`perf/move-face-color-buffer` ([draft PR #68](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/68)).

After a local Move, most loose faces keep the same geometry and paint, yet
`bucket_face` rebuilt their shaded colour triangles on every content revision.
This branch retains the packed front-colour bytes on an active-mesh `Face`
while its complete outer/hole geometry signature and effective front colour
match. An edited face or changed paint rebuilds its bytes. Back, texture,
opacity and visibility decisions still run on each paint, so they can route
the same front bytes to the correct draw pass. Preview and group faces do not
keep this cache. Active mesh switches and the existing 20,000-face cap release
entries; each retained entry is capped at 512 bytes, or at most about 10 MB
across the capped active mesh.

The bundled `pileta-fuente-yanque.igz` example has 7,633 loose faces after
one detached triangle is added for a planar Move. A native Windows 640x480
direct `paintGL` probe measured 424 ms median with the cache versus 518 ms
with uncached block packing restored in the same process, over five trials
per mode. Command time stayed around 15-16 ms. This excludes input dispatch,
Qt scheduling, buffer swap and display scanout; it is not user-visible
latency. A profiler had attributed 0.618 of 0.748 profiled seconds to
`bucket_face` before this change. Profiler overhead makes those numbers
unsuitable as an absolute wall-clock baseline.

Targeted face, material, texture and render tests passed 113 with two platform
skips. New tests cover unrelated Move reuse, changed geometry and colour,
Undo/Redo, active mesh switches and the face-count cap. `compileall` and
`git diff --check` passed. CI run 37613474489 was cancelled when the
documentation commit triggered a newer run. Hosted
[run 37614332399](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/actions/runs/37614332399)
passed Windows Qt offscreen smoke and Ubuntu `pytest (not slow)` at `29ebfea`.

Next measure remaining face visibility and GPU draw costs, then capture real
input-to-visible-pixel latency on a representative model. The installed
`C:\Program Files\IngeTrazo` build remains at `3815ef8`.
