# Faster loose-edge rebuild after Move

Base: draft PR #66 (`perf/move-face-geometry-cache`). Branch:
`perf/move-loose-edge-render` ([draft PR #67](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/67)).

Each content revision invalidates the viewport's loose hard-edge block. The
old rebuild asked `Scene.entity_visible()` about every edge before discarding
soft and hidden edges. The bundled `pileta-fuente-yanque.igz` contains a
15,312-edge mesh whose edges are all soft, so that visibility scan produced
no GPU lines. The rebuild now skips soft/hidden edges first and resolves Tag
visibility once per Tag for an unmodified `Scene`. A customized visibility
predicate retains the public method path. Duplicate Tag names keep the first
Tag's visibility, matching `Scene.layer()`; unknown Tags remain visible.

On native Windows, repeated forced rebuilds of that example mesh measured a
median of about 72 ms before and 0.3 ms after over ten post-warm-up trials.
With all 15,312 edges forced hard, the new rebuild measured about 30 ms. A
separate 640x480 native OpenGL probe with one detached triangle measured
median direct `paintGL` after Move at 508 ms over three trials, versus 576 ms
with the old edge path restored in the same session. The probe excludes input
dispatch, Qt scheduling, buffer swap and display scanout. These small samples
indicate renderer cost, not measured user-visible latency.

Focused Tag/hide/cache tests passed 27/27. Broader render/pick tests passed
18 with five platform skips. New coverage checks Tag visibility changes and
Hide/Undo. `compileall` and `git diff --check` passed. Hosted CI is pending.

Next, profile face bucketing and edge draw cost on a model with hard edges,
then measure actual input-to-visible-pixel latency in the installed GUI. The
installed `C:\Program Files\IngeTrazo` build remains at `3815ef8`.
