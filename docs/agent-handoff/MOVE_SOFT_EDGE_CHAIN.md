# Preserve loose silhouette arrays through coalesced Moves

Base: [draft PR #77](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/77)
(`perf/move-soft-edge-cache`). Delivery:
[draft PR #78](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/78)
(`perf/move-soft-edge-chain`), implementation commit `1c64443`.

PR #77 reuses loose soft-edge arrays across one exact safe Move transition.
If several safe Moves happen before Qt paints, its marker points only to the
last step. The viewport's arrays from the earlier paint then miss the marker
and are rebuilt. This change composes adjacent safe transitions by keeping
their first scene version and mesh serial. The viewport records that chain
origin alongside its cached arrays after each paint, so a subsequent safe
Move or Undo can still reuse them. Only a position-only Move that changes no
soft-edge endpoint or adjacent Face plane joins the chain. A non-Move scene
edit, changed mesh, custom visibility path or unsafe Move breaks reuse.

Regression tests cover two safe Moves before paint, repeated paints during
Undo/Redo, a changed Face plane, custom visibility, and an intervening scene
version change. The 53 focused native Windows Move/silhouette/group/document
cache tests passed. `compileall` and `git diff --check` passed.

`scripts/bench_move_soft_chain.py` compares this path with PR #77's
single-transition marker. It performs three synthetic safe Moves within one
queued Qt action before painting, alternates order, and uses the bundled
Yanque model's 15,312 loose soft edges. Three samples per run and two rounds
gave these medians of run medians:

| Path | Paint | Queued Moves to `frameSwapped` | Array builds per run |
| --- | ---: | ---: | ---: |
| Single transition | 134.738 ms | 189.640 ms | 7 |
| Chained | 74.713 ms | 127.799 ms | 1 |

These are local 640x480 native Qt frame-submission measurements. They do not
measure a real Move tool's pointer delivery, picking or monitor scanout. A
shorter two-sample check also favored chaining (184.424 to 119.822 ms), but
neither check proves the same gain across other meshes. The installed
`C:\Program Files\IngeTrazo` build remains at `3815ef8`.

PR #77 final-head hosted [run 37719319412](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/actions/runs/37719319412)
passed Ubuntu `pytest (not slow)` and Windows Qt smoke. PR #78 code-head
[run 37722206460](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/actions/runs/37722206460)
was in progress at this snapshot. Verify final-head CI after this document
is pushed, then test a real drag and complex project topology.
