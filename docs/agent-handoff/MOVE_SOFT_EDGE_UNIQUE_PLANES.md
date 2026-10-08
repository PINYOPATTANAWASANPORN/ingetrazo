# Compute loose silhouette planes once per Face

Base: draft PR #75 (`perf/vbo-changed-tail`). Branch:
`perf/soft-edge-unique-planes` ([draft PR #76](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/76)).

`_loose_soft_edge_arrays` used to gather a full triangle for both sides of
every soft edge, then cross both gathered arrays. Adjacent edges often share
a Face. The new path crosses each unique Face plane once and gathers only
normals and anchors per edge. The six returned arrays keep their order,
shape and values; empty, boundary, shared, and non-manifold cases are covered
by the existing silhouette tests.

On the bundled Yanque example's 15,312 loose soft edges and 7,632 faces,
all six arrays matched the previous function exactly. A 20-trial alternating
native Windows comparison measured 55.05 ms old versus 54.686 ms new for
the isolated array preparation. A one-call `tracemalloc` comparison measured
13.47 MiB old versus 10.53 MiB new peak traced allocation (both returned
1.77 MiB of arrays). Tracing itself raised the measured runtime. Four
three-trial native Qt frame runs ranged from 128.648 to 162.028 ms paint
median across both variants and cannot establish a frame-latency gain.

Validation: 50 focused native Windows tests passed, with three platform
skips. `compileall` and `git diff --check` passed. PR #75's final-head CI
[run 37711369473](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/actions/runs/37711369473)
passed both Ubuntu `pytest (not slow)` and Windows Qt smoke. PR #76 CI is
pending at this snapshot. The installed `C:\Program Files\IngeTrazo` build
remains at `3815ef8`.

Next: profile Python edge/Face collection within silhouette preparation and
the loose-face bucketing path on representative large meshes. Keep the
queued Move-to-`frameSwapped` measure separate from direct paint timing.
