# SPDX-License-Identifier: GPL-3.0-or-later
"""Edit ▸ Select By: direct filters that need no seed selection."""
from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QMatrix4x4, QVector3D
from PySide6.QtWidgets import QApplication

if QApplication.instance() is None:
    QApplication(sys.argv[:1])

from core.group import Group
from core.layers import Layer, assign_layer
from core.mesh import Mesh
from core.scene import Scene
from core.select_ops import by_layer, by_material, by_type


def V(x, y, z=0.0):
    return QVector3D(float(x), float(y), float(z))


def _face(mesh, x=0.0):
    return mesh.add_face([V(x, 0), V(x + 1, 0),
                          V(x + 1, 1), V(x, 1)])


def test_type_filter_distinguishes_groups_and_components():
    scene = Scene()
    face = _face(scene.mesh)
    group = Group(Mesh(), name="Group")
    component = Group(Mesh(), name="Component")
    component.xform = QMatrix4x4()
    scene.groups.extend([group, component])

    assert by_type(scene, "faces") == [face]
    assert by_type(scene, "groups") == [group]
    assert by_type(scene, "components") == [component]


def test_layer_filter_respects_hidden_and_locked_tags():
    scene = Scene()
    scene.layers.extend([Layer("Walls"), Layer("Hidden", visible=False),
                         Layer("Locked", locked=True)])
    wall = _face(scene.mesh, 0)
    hidden = _face(scene.mesh, 2)
    locked = _face(scene.mesh, 4)
    for entity, name in ((wall, "Walls"), (hidden, "Hidden"),
                         (locked, "Locked")):
        assign_layer(entity, name)

    assert by_layer(scene, "Walls") == [wall]
    assert by_layer(scene, "Hidden") == []
    assert by_layer(scene, "Locked") == []


def test_material_filter_handles_named_default_and_group_paint():
    scene = Scene()
    brick = _face(scene.mesh, 0)
    default = _face(scene.mesh, 2)
    brick.attrs["mat"] = "Brick"
    group = Group(Mesh(), name="Painted")
    group.material = {"mat": "Brick"}
    scene.groups.append(group)

    assert set(by_material(scene, ("mat", "Brick"))) == {brick, group}
    assert by_material(scene, None) == [default]


def test_menu_selects_without_a_seed_selection():
    from views.main_window import MainWindow
    win = MainWindow()
    try:
        scene = win.viewport.scene
        a = _face(scene.mesh, 0)
        _face(scene.mesh, 2)
        a.attrs["mat"] = "Brick"

        win._fill_select_by_menu()
        submenus = {a.text(): a.menu()
                    for a in win._select_by_menu.actions()}
        material_menu = submenus["Material"]
        next(a for a in material_menu.actions()
             if a.text() == "Brick").trigger()

        assert scene.selection == {a}
        assert win.statusBar().currentMessage()
    finally:
        win._saved_version = win.viewport.scene.version
        win.close()
