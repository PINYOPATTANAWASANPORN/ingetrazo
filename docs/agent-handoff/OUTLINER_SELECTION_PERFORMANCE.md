# Outliner selection synchronization performance

Base: draft PR #56 (`fix/outliner-nested-selection`).
Branch: `perf/outliner-selection-sync`.

## Change

Viewport selection changes now map selected objects through the Outliner row
index and change only rows whose selected state differs. The row index is
rebuilt whenever the tree is rebuilt. The previous implementation called
`setSelected` on every row for each viewport selection change.

## Evidence

A local, offscreen Windows synthetic scene with 2,000 top-level groups and
100 successive single-object selection changes measured 1.6936 seconds on
the parent implementation and 0.0012 seconds with this change. This measures
selection synchronization only, excludes tree construction and rendering,
and is not a whole-application speedup claim. The benchmark script is outside
the repository at `C:\Users\Lenovo\Desktop\IngeTrazoTest\bench-outliner-sync.py`.
Ten Outliner tests passed with native Windows Qt and ten with offscreen Qt.
The new test covers adding/removing rows and repeated unchanged sync.

## Remaining

Validate with representative large documents and profile tree refresh,
filtering, rendering and face/edge hierarchy separately. Installed binary
is unchanged.
