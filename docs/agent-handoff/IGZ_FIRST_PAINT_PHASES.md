# Native IGZ first-paint phase profile

Draft PR #94, stacked on #93, adds an opt-in
`--profile-phases` mode to the same fresh-process benchmark. It captures
existing viewport telemetry in memory for the **matching first model paint**
and adds four subphases inside `_sync_edges`. No document is saved. Normal
benchmark runs leave viewport telemetry disabled. Run on a visible native
Windows desktop:

```powershell
python scripts/bench_igz_first_frame.py --repeats 3 --profile-phases --output first-paint-phases.json
```

Windows 10 build 19045, Python 3.12.15, three fresh processes per SHA-pinned
example. Medians below are milliseconds; all nine samples and source hashes
are in `benchmarks/results/igz-windows-first-paint-phases-2026-10-09.json`.

| Model | Model paint | `_sync_edges` | Edge-block phase | Chunk rebuilds | Face draw phase |
| --- | ---: | ---: | ---: | ---: | ---: |
| banca-pergola | 94.837 | 32.761 | 32 | 30.895 (7) | 18 |
| pileta-fuente | 1,328.279 | 1,246.263 | 1,244 | 1,132.497 (34) | 24 |
| arco | 734.792 | 649.447 | 648 | 611.563 (28) | 81 |

The initial edge-block phase calls `_group_chunk` for visible groups, builds
the combined hard-edge buffer and uploads it. The later face-block phase
mostly reuses those chunks. On pileta and arco, the measured chunk rebuilds
account for most of the first model paint, making cold render-chunk preparation
the next optimization target. The `chunk_rebuild` count includes short builds:
an earlier thresholded log showed only the seven longest pileta builds and
therefore understated their combined cost. One pileta group was read from disk
cache in these runs; the benchmark does **not** guarantee an empty chunk cache
because the cache directory can live outside the temporary application profile.

This is a diagnostic profile, not a before/after speedup claim. Viewport phase
records are rounded to whole milliseconds, while total and chunk timings keep
sub-millisecond precision. Existing timers nest: do not sum `_sync_edges`,
`edge_blocks` and `chunk_rebuild` as independent costs. Disk and OS caches
were not flushed, and none of the three bundled files is a genuinely large
nested project. The first-frame signal is Qt submission, not monitor scanout.

Next implementation slice: reduce cold `_group_chunk` preparation or build a
bounded progressive render path, then repeat the **unprofiled** first-frame
baseline and a visual/correctness gate on a large nested model. The large-model
workstream remains at 70%; the installed application remains unchanged.

The next slice, `IGZ_FLAT_PICK_TRIANGLES.md`, isolates the chunk cache per
benchmark process and compares a flat pick-triangle representation against
its preceding code. Those cold-cache numbers are not directly comparable to
this earlier profile, which could reuse a persistent disk chunk.
