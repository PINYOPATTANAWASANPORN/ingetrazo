# Cold IGZ chunk: flat pick triangles

This bounded follow-up to `IGZ_FIRST_PAINT_PHASES.md` changes the cold
`_group_chunk` build. Pick triangles previously became a nested Python list
(`triangle → three vertices → three coordinates`) before NumPy converted the
whole list to `float64`. They now accumulate in a flat `array('d')`; NumPy
views the completed buffer as `(triangles, 3, 3)`. The resulting `v0`, `e1`,
`e2`, face indices, default-back tint and on-disk chunk format retain their
existing contracts.

The native first-frame runner now assigns a fresh
`INGETRAZO_TEXTURE_CACHE` directory to **each** child process. Qt's generic
data location can otherwise resolve outside the temporary application
profile, allowing one sample to reuse an older disk chunk. Both files below
were measured with that cache isolation, with diagnostic phase profiling off.
Each has three SHA-verified samples per bundled IGZ on the same Windows 10
machine. They are in `benchmarks/results/` as
`igz-windows-cold-chunk-before-2026-10-09.json` and
`igz-windows-cold-chunk-after-2026-10-09.json`.

| Model | Paint before → after | Qt frame before → after |
| --- | ---: | ---: |
| banca-pergola | 95.571 → 105.546 ms | 358.870 → 364.641 ms |
| pileta-fuente | 1,912.665 → 1,712.007 ms | 3,450.894 → 3,153.848 ms |
| arco | 816.083 → 679.700 ms | 1,669.060 → 1,445.391 ms |

These are medians of sequential three-run batches, not an interleaved or
statistically powered performance experiment. The two slower examples show
roughly 10% and 17% lower model-paint time, respectively. The small model
varied upward by about 10 ms. OS caches and background load were not
controlled, so repeat on a genuinely large nested project before treating
the change as a release-level gain. The older first-frame and phase results
used the previous cache setup and should not be compared directly with these
cold-cache measurements.

Validation: 61 face-side, pick, chunk and instance tests passed; a further 31
pick/cache tests passed with one skip; two corpus tests passed; Python compile
and diff checks passed. The installed application was not updated. Large-model
performance remains at 70% because progressive painting and a real nested
project correctness/performance gate are still open.
