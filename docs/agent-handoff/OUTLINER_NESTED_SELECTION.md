# Nested Outliner selection follow-up

Base: PR #55 (`ci/windows-qt-gate`), verified CI at `1b8dfb2`.
Branch: `fix/outliner-nested-selection`.

## Corrected behavior

- Search previously used `any(generator)` while recursively updating rows.
  The first matching child short-circuited the traversal, leaving later
  siblings stale. Every child is now visited, including when clearing search.
- Cross-parent multi-selection was reduced in the viewport but not in the
  tree. Context-menu hide/lock could therefore affect extra rows. After
  choosing the supported edit context, tree selection now matches it.
- Locked-row inspection/unlock behavior remains unchanged. This does not
  introduce editing across multiple coordinate contexts.

## Evidence

Nine Outliner tests passed with native Windows Qt and nine with offscreen.
Both new tests fail against the parent implementation and pass with the fix.
The tests cover nested search transitions, clearing the query, cross-level
selection, hide targets and Undo. They do not replace manual GUI or large
model validation. No installed executable was changed.

## Remaining scope

Face/Edge hierarchy, large-tree performance, navigation breadcrumbs and
richer nested-selection UX remain open. No completion percentage increased.
