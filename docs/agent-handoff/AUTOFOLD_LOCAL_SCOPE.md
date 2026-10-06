# Scope Move Autofold to the touched faces

Base: draft PR #62 (`test/autofold-holed-nonmanifold`).
Branch: `perf/move-local-autofold`.

Move's preview inspects only the faces incident to the moved vertices, but
the old commit called `fold_nonplanar_faces` on every face in the loose mesh.
A new regression reproduces the mismatch: moving one corner folded an
unrelated, pre-existing warped quad far away. The test fails on the parent
code and passes after this change.

`translate_points` optionally returns the incident faces collected before
translation. `MoveVerticesCommand` passes those faces to Autofold. The
default full-mesh behavior remains for the other callers; Push/Pull's live
preview does not pay for face collection. This changes only the fold-check
scope of a Move command, not the move or undo snapshot semantics.

Validation: 267 transform and Push/Pull tests passed on native Windows Qt;
183 tests passed in the expanded Windows CI selection locally offscreen.
The benchmark command is:

```text
python scripts/bench_move_autofold_scope.py examples/pileta-fuente-yanque.igz
```

Seven sequential in-memory trials on Windows, timing only the Autofold phase:

| Example | Mesh faces | Incident faces | Full scan median | Local median |
| --- | ---: | ---: | ---: | ---: |
| `pileta-fuente-yanque.igz` | 7,632 | 4 | 77.089 ms | 0.774 ms |
| `arco-yanque.igz` | 1,500 | 3 | 16.069 ms | 0.355 ms |

The command loads the example once and restores identical in-memory mesh
state between measurements. Loading, vertex translation, snapshots, and
viewport painting are excluded; these figures are **not** total Move latency
or an end-to-end model-open benchmark. Both paths folded two source faces
and produced the same resulting face count in each example. No installed
binary changed.
