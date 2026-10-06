# Tag selection consistency for annotations

Base: draft PR #58 (`perf/outliner-incremental-refresh`).
Branch: `fix/tag-annotation-selection`.

Hiding or locking a Tag previously removed selected faces, edges and groups,
but left selected dimensions and text labels on that Tag. The selection
pruning now applies to every selected entity carrying the Tag. Assigning
selected entities to a hidden or locked Tag through the Tags panel or
Entity Info also clears their selection after the undoable assignment.

The regression test failed on the parent code with Dimension and TextLabel
still selected. The focused layers, active-layer containers and assignment
suite passed 25 tests with native Windows Qt and 25 with offscreen Qt.
Tests cover Hide/Lock, assignment through both UI routes and undo of the
Tag assignment. This is not an installed-binary validation. Further complex
Tag workflows and rendering checks remain open.
