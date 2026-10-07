# Rebuild loose soft-edge silhouettes after Move

Base: draft PR #70 (`perf/move-face-signature-tuples`). Branch:
`perf/move-silhouette-rebuild` ([draft PR #71](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/71)).

After a local Move, every loose soft edge still passed through
`Scene.entity_visible()` and the profile-plane preparation repeatedly built
temporary `Face.vertices` lists and called three scalar Qt getters per point.
The renderer now snapshots Tag visibility once per rebuild for a plain Scene,
while custom visibility predicates use the public method. It reads shared
vertex positions directly through `QVector3D.toTuple()` and reuses the first
face plane for one-face and non-manifold edges. The one-, two-, and many-face
profile classification and edge flags are unchanged. The custom-predicate
fallback retains the original call order, including isolated soft edges
before the incidence check.

On the bundled `pileta-fuente-yanque.igz` mesh plus one detached triangle
(7,633 faces, 15,312 soft edges), native Windows 640x480 direct `paintGL`
after Move measured 306.5 ms before versus 159.5 ms after. The silhouette
substep measured 214.9 ms before versus 83.5 ms after. Each is a median of
seven trials in a separate process. The probe excludes input dispatch, Qt
scheduling, buffer swap and display scanout, so it is not user-visible latency.
An isolated same-process eight-repetition A/B on the 15,312 candidate edges
confirmed identical edge identities and exact NumPy arrays: visibility
filtering was 75.0 ms old versus 2.1 ms new; plane-array preparation was
121.6 ms old versus 78.3 ms new (medians, alternating order).

Regression tests compare candidate edges with `Scene.entity_visible()` for
hidden, locked, unknown and duplicate Tags, custom predicates, and soft/hidden
flags. Profile plane arrays match the prior one-, two-, and many-face math.
Relevant geometry, Tag, Hide and render tests passed 105, with four platform
skips. `compileall` and `git diff --check` passed. Hosted CI run
[37651695134](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/actions/runs/37651695134)
passed Ubuntu `pytest (not slow)` and Windows Qt offscreen smoke on code
commit `67ac1f9c6b4265deb974a237b7c4a430ed0ab8e2`.

A post-change `cProfile` paint attributed 0.248 of 0.384 profiled seconds to
`_sync_edges` (0.221 cumulative in Face bucketing), versus 0.133 to the
silhouette pass. These are profiler timings, not wall-clock measurements.
Next profile Face bucketing and measure input-to-visible-pixel latency in a
real GUI interaction. The installed `C:\Program Files\IngeTrazo` build
remains at `3815ef8`.
