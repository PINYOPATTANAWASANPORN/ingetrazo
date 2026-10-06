# Position-only snapshots for plain Move

Base: draft PR #63 (`perf/move-local-autofold`). Branch:
`perf/move-position-snapshot` ([draft PR #64](https://github.com/PINYOPATTANAWASANPORN/ingetrazo/pull/64)).

The scoped Autofold check removed the whole-mesh face scan, but a plain Move
still captured the entire mesh twice for Undo/Redo. On the bundled 7,632-face
example, one full snapshot took roughly 30 ms. That cost scaled with unrelated
model geometry even when the command moved one vertex and changed no topology.

Move now identifies its vertices and incident faces before mutation, then
projects the exact `QVector3D` positions that `mesh.move_vertex` will write.
If every touched face stays planar, it saves only the moved vertex positions
and a copy of the vertex registry before and after the edit. The registry is
needed when a moved vertex lands on another vertex's key: inverse translation
or a lookup by position would not restore the right object. The small snapshot
preserves object identity, and restore dirties the mesh render cache.

If any touched face could be nonplanar, Move retains the full identity-
preserving snapshots and the existing Autofold operation. This deliberately
includes degenerate faces that may not ultimately fold. Edits touching more
than 256 faces also keep the full path, because projecting thousands of faces
can cost more than the snapshot it replaces. The change does not alter
`Mesh.capture_state` for other commands.

Validation on Windows: 223 Move, Push/Pull, mesh, attributes and layer tests
passed natively. The regression asserts full mesh-state equality after
Undo/Redo when a moved vertex lands on a stationary vertex, and verifies that
a warping quad and broad selection still use full topology snapshots. The
offscreen Windows CI selection passed 189 tests locally with `PYTHONUTF8=1`;
it now includes `test_move_undo.py`. Without that environment setting, two
unrelated packaging tests fail when Windows defaults to Thai `cp874` for UTF-8
files.

Run `python scripts/bench_move_position_snapshot.py
examples/pileta-fuente-yanque.igz` to compare the old full-snapshot command
path with the position-only path. It loads the example, adds one detached
triangle **in memory**, and moves one triangle corner so the surrounding
real mesh is unrelated to the edit. Seven interleaved trials on 2026-10-07:

| Example mesh | Full Move `do` | Position-only `do` | Full Undo | Position-only Undo |
| --- | ---: | ---: | ---: | ---: |
| 7,633 faces | 90.135 ms | 15.336 ms | 20.698 ms | 0.069 ms |
| 1,501 faces | 14.800 ms | 4.209 ms | 3.750 ms | 0.020 ms |

These timings exclude loading, viewport paint, and user input. They measure
the plain path with a synthetic detached triangle, so they do not describe
how often real user moves qualify for that path. A move that folds still pays
for full snapshots; `bench_move_command.py` measures that separate case.
The installed `C:\Program Files\IngeTrazo` build remains `3815ef8`.
