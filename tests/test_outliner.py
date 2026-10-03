# SPDX-License-Identifier: GPL-3.0-or-later
"""The model Outliner exposes the whole nested group tree."""
from __future__ import annotations

from PySide6.QtCore import Qt

from core.group import Group
from core.history import History, LockGroupsCommand
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
