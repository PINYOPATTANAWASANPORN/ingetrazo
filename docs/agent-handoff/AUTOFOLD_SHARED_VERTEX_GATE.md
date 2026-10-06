# Multi-face Autofold integration gate

Base: draft PR #60 (`fix/active-tag-indicator`).
Branch: `test/autofold-shared-vertex-grid`.

A new integration test lifts the shared center vertex of a 3 × 3 quad grid.
Four incident faces fold; the test compares all preview fold edges against
the newly committed edges, checks every resulting face is planar, ensures
edge incidence remains at most two, verifies per-face material attributes,
and checks one-step Undo/Redo restores the expected grid and folded state.
The fixture exercises shared topology, not just one isolated quad.

The four relevant Move/Autofold suites passed 59 tests on native Windows Qt
and 59 offscreen. The Windows hosted offscreen smoke workflow now includes
these four files. Its expanded local selection passed 179 tests in 42.24 s
with `QT_QPA_PLATFORM=offscreen`; hosted validation is pending. No product
geometry code changed because the new stress case passed as implemented.

Remaining: non-manifold and holed-face behavior, larger real meshes, and
explicit user controls for Autofold. The installed build is unchanged.
