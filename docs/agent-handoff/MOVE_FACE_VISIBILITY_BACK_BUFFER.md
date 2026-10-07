# Batch face visibility and reuse default-back geometry

Base: draft PR #68 (`perf/move-face-color-buffer`). Branch:
`perf/move-face-visibility-back-buffer` ([draft PR #69](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/69)).

After the front-colour cache, a local Move still called
`Scene.entity_visible()` for every loose face and repacked position-only
triangles for its default back. The renderer now snapshots Tag visibility once
per rebuild for an unmodified `Scene`, matching hidden Face attributes,
unknown Tags and the first of duplicate Tag names. Subclasses and scenes with
customized visibility predicates still use `entity_visible()`. The
default-back position block is retained on a Face while its complete
outer/hole geometry signature matches. Edited faces rebuild normally. Cache
entries are released when the active mesh changes or exceeds the existing
20,000-face cap; each retained back block is limited to 512 bytes.

On the bundled `pileta-fuente-yanque.igz` example plus one detached triangle
(7,633 loose faces), native Windows 640x480 direct `paintGL` after Move
measured 370 ms with the old visibility/back paths versus 270 ms with these
changes, medians of five trials in one process. Reversing the measurement
order gave 408 ms versus 298 ms. Command time stayed near 16 ms. The probe
excludes input dispatch, Qt scheduling, buffer swap and display scanout.
It does not measure user-visible latency.

Relevant face, Tag, Hide, material, texture and render tests passed 145, with
three platform skips. New coverage checks hidden, locked, missing and
duplicate Tags, Hide/Undo, customized visibility, changed geometry,
Move/Undo/Redo, active-mesh switches and the cache cap. `compileall` and
`git diff --check` passed. Hosted CI run
[37616572439](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/actions/runs/37616572439)
passed Ubuntu `pytest (not slow)` and Windows Qt offscreen smoke on code commit
`56b7468b4fd0032532df09a711aac33ac4fd4e54`.

Next profile remaining GPU draw work and measure actual input-to-visible-pixel
latency on a representative model. The installed
`C:\Program Files\IngeTrazo` build remains at `3815ef8`.
