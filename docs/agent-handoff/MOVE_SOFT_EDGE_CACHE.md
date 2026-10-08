# Reuse loose soft-edge arrays after unrelated Moves

Base: [draft PR #76](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/76)
(`perf/soft-edge-unique-planes`). Delivery:
[draft PR #77](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/77)
(`perf/move-soft-edge-cache`), implementation commit `89532f4`.

The loose silhouette array cache used to rebuild after every vertex Move,
even if the moved vertex touched no soft edge and changed no Face plane that
a soft edge uses. `MoveVerticesCommand` now records a narrowly scoped
old-to-new scene-version and loose-mesh-serial transition only when its moved
vertices and touched Faces cannot change these arrays. The viewport accepts
that exact transition when the cached arrays belong to the same mesh and the
standard scene visibility path is active. It falls back to a rebuild for a
soft-edge endpoint, a Face-plane change, different mesh/visibility path, or
an intervening scene edit. Undo and redo use the same test.

The focused regression covers safe Move, Undo, Redo, custom visibility,
intervening scene mutation, and a moved Face vertex that does not lie on a
soft-edge endpoint. The latter must rebuild because it changes the Face
plane. All 52 focused Move/silhouette/group/document-cache tests passed on
native Windows; `compileall` and `git diff --check` passed.

`scripts/bench_move_soft_cache.py` runs the old forced-rebuild and new cache
paths in alternating order against the bundled Yanque sample (15,312 loose
soft edges). With five queued Move frames per run and two rounds, the median
of run medians changed as follows:

| Path | Paint | Queued Move to `frameSwapped` | Array builds |
| --- | ---: | ---: | ---: |
| Forced rebuild | 147.126 ms | 167.246 ms | 11 |
| Cache reuse | 87.764 ms | 106.532 ms | 1 |

A second three-repeat, two-round run also favored reuse (123.412 to
76.866 ms paint; 143.56 to 96.49 ms Move-to-swap). These are local native
Qt frame-submission measurements, not physical pointer-to-visible-pixel
latency. The gain applies only to Moves proved independent of the loose
soft-edge arrays; other edits still rebuild. No independent CI performance
benchmark or complex real-project topology test has been completed.

At this snapshot, PR #76 final-head CI
[run 37715521408](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/actions/runs/37715521408)
and PR #77 code-head CI
[run 37719025557](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/actions/runs/37719025557)
were in progress. Recheck final-head CI after documentation lands. The
installed `C:\Program Files\IngeTrazo` build remains at `3815ef8`.
