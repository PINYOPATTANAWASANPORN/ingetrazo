# SPDX-License-Identifier: GPL-3.0-or-later
"""The model Outliner exposes the whole nested group tree."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from core.group import Group
from core.history import History, LockGroupsCommand, ReorderGroupCommand
from core.scene import Scene
from formats import igz
from views.tray import OutlinerPanel


class _Viewport:
    def __init__(self, scene):
        self.scene = scene
        self.history = History(scene)
        self.updates = 0

    def update(self):
        self.updates += 1

    def end_group_edit(self):
        self.scene.end_group_edit()

    def begin_group_edit(self, group):
        self.scene.begin_group_edit(group)


class _Window:
    def __init__(self, scene):
        self.viewport = _Viewport(scene)
        self.zoomed = 0

    def _on_zoom_selection(self):
        self.zoomed += 1


def _model():
    scene = Scene()
    leaf = Group(name="Chair leg")
    chair = Group(name="Chair")
    chair.adopt([leaf])
    room = Group(name="Room")
    room.adopt([chair])
    tree = Group(name="Tree")
    scene.groups.extend([room, tree])
    return scene, room, chair, leaf, tree


def test_tree_contains_every_nested_group_and_search_keeps_ancestors():
    scene, room, chair, leaf, tree = _model()
    panel = OutlinerPanel(_Window(scene))
    assert panel.tree.topLevelItemCount() == 2
    assert panel._items[id(room)].child(0).data(0, Qt.UserRole) is chair
    assert panel._items[id(chair)].child(0).data(0, Qt.UserRole) is leaf

    panel.search.setText("leg")
    assert not panel._items[id(room)].isHidden()
    assert not panel._items[id(chair)].isHidden()
    assert not panel._items[id(leaf)].isHidden()
    assert panel._items[id(tree)].isHidden()


def test_selecting_nested_row_opens_its_parent_path():
    scene, room, chair, leaf, _tree = _model()
    win = _Window(scene)
    panel = OutlinerPanel(win)
    panel._items[id(leaf)].setSelected(True)
    assert [level["group"] for level in scene._edit_stack] == [room, chair]
    assert scene.edit_group is chair
    assert scene.selection == {leaf}


def test_search_updates_every_sibling_and_clearing_restores_nested_rows():
    scene, room, chair, leaf, _tree = _model()
    table = Group(name="Table")
    room.adopt([chair, table])
    panel = OutlinerPanel(_Window(scene))
    try:
        # A hit in the first child must not leave later siblings visible.
        panel.search.setText("leg")
        assert not panel._items[id(leaf)].isHidden()
        assert panel._items[id(table)].isHidden()
        # Switching the hit must revisit both branches.
        panel.search.setText("table")
        assert panel._items[id(chair)].isHidden()
        assert not panel._items[id(table)].isHidden()
        panel.search.clear()
        assert all(not item.isHidden() for item in panel._items.values())
    finally:
        panel.close()
        panel.deleteLater()


def test_cross_level_selection_matches_viewport_and_bulk_action_targets():
    scene, room, chair, leaf, tree = _model()
    win = _Window(scene)
    panel = OutlinerPanel(win)
    try:
        panel.tree.blockSignals(True)
        panel._items[id(leaf)].setSelected(True)
        panel._items[id(tree)].setSelected(True)
        panel.tree.blockSignals(False)
        panel._on_selection_changed()
        selected = set(scene.selection)
        assert len(selected) == 1
        assert set(panel._selected_groups()) == selected
        panel._set_hidden(panel._selected_groups(), True)
        assert {g for g in (room, chair, leaf, tree) if g.hidden} == selected
        assert win.viewport.history.undo()
        assert not any(g.hidden for g in (room, chair, leaf, tree))
    finally:
        panel.close()
        panel.deleteLater()


def test_visibility_lock_and_rename_are_undoable():
    scene, room, _chair, _leaf, _tree = _model()
    win = _Window(scene)
    panel = OutlinerPanel(win)
    item = panel._items[id(room)]

    item.setText(0, "Ground floor")
    assert room.name == "Ground floor"
    win.viewport.history.undo()
    assert room.name == "Room"
    panel.refresh()

    panel._items[id(room)].setCheckState(1, Qt.Unchecked)
    assert room.hidden and room not in scene.selection
    win.viewport.history.undo()
    assert not room.hidden
    panel.refresh()

    panel._items[id(room)].setCheckState(2, Qt.Checked)
    assert room.locked and not scene.entity_selectable(room)
    QApplication.processEvents()  # queued tree rebuild must not delete the active item
    assert panel._items[id(room)].checkState(2) == Qt.Checked
    win.viewport.history.undo()
    assert not room.locked and scene.entity_selectable(room)


def test_locked_group_round_trips_and_copy_keeps_lock(tmp_path):
    scene, room, chair, _leaf, _tree = _model()
    History(scene).execute(LockGroupsCommand([chair]))
    path = tmp_path / "locked.igz"
    igz.save_scene(scene, path)
    loaded = Scene()
    igz.load_into(loaded, path)
    loaded_chair = loaded.groups[0].children[0]
    assert loaded_chair.locked
    assert not loaded.entity_selectable(loaded_chair)

    from core.group import copy_group
    assert copy_group(chair).locked


def test_locked_ancestor_blocks_selecting_a_nested_row():
    scene, room, _chair, leaf, _tree = _model()
    room.locked = True
    panel = OutlinerPanel(_Window(scene))
    panel._items[id(leaf)].setSelected(True)
    assert not scene._edit_stack
    assert not scene.selection


def test_reorder_command_moves_siblings_and_undoes_at_both_levels():
    scene, room, chair, leaf, tree = _model()
    other = Group(name="Table")
    room.children.append(other)
    history = History(scene)

    history.execute(ReorderGroupCommand(scene.groups, tree, 0))
    assert scene.groups == [tree, room]
    history.undo()
    assert scene.groups == [room, tree]
    history.redo()
    assert scene.groups == [tree, room]

    history.execute(ReorderGroupCommand(room.children, other, 0))
    assert room.children == [other, chair]
    assert chair.children == [leaf]
    history.undo()
    assert room.children == [chair, other]


def test_outliner_drop_reorders_only_siblings():
    scene, room, chair, leaf, tree = _model()
    table = Group(name="Table")
    scene.groups.append(table)
    panel = OutlinerPanel(_Window(scene))

    panel._on_drop_reorder(panel._items[id(table)],
                           panel._items[id(room)], after=False)
    assert scene.groups == [table, room, tree]
    panel._window.viewport.history.undo()
    assert scene.groups == [room, tree, table]

    panel.refresh()
    panel._on_drop_reorder(panel._items[id(room)],
                           panel._items[id(tree)], after=True)
    assert scene.groups == [tree, room, table]
    panel._window.viewport.history.undo()
    assert scene.groups == [room, tree, table]

    # A cross-level drop must not silently change coordinate frames.
    panel.refresh()
    panel._on_drop_reorder(panel._items[id(tree)],
                           panel._items[id(leaf)], after=False)
    assert scene.groups == [room, tree, table]
    assert chair.children == [leaf]
