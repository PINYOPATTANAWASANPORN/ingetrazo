# Active Tag indicator consistency

Base: draft PR #59 (`fix/tag-annotation-selection`).
Branch: `fix/active-tag-indicator`, draft PR #60.

The Layers panel's active dot previously stayed on the old Tag when the
panel's Set active button changed the drawing Tag. Hiding or locking the
active Tag moved `scene.active_layer` to the default and updated the toolbar,
but left the panel marker stale. The panel now updates only the active-dot
cells in place, avoiding tree deletion inside Qt's itemChanged callback.

The regression test switches the Tag, then locks and hides it, checking the
scene, panel markers and toolbar selector. The focused Layers, active-layer
containers and assignment suite passed 25 tests on native Windows Qt and
25 offscreen. The installed executable is unchanged. Other complex Tag
workflows remain to be validated.
