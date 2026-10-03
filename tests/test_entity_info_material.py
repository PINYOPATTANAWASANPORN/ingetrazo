# SPDX-License-Identifier: GPL-3.0-or-later
"""Entity Info assigns one material to faces and objects together."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QVector3D
from PySide6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication([])

from core.group import Group
from core.materials import Material
from core.mesh import Mesh


def V(x, y, z=0.0):
    return QVector3D(float(x), float(y), float(z))


def _face(mesh, x=0.0):
    return mesh.add_face([V(x, 0), V(x + 1, 0),
                          V(x + 1, 1), V(x, 1)])


def _window():
    from views.main_window import MainWindow
    win = MainWindow()
    win.show()
    _app.processEvents()
    return win


def test_mixed_faces_and_groups_take_one_material_and_undo():
    win = _window()
    vp = win.viewport
    try:
        scene = vp.scene
        brick = Material("Brick", color=(0.7, 0.2, 0.1), opacity=0.8)
        scene.materials[brick.name] = brick
        face = _face(scene.mesh)
        face.attrs.update({"color": (0.1, 0.2, 0.3), "mat": "Old"})
        group = Group(Mesh(), name="Wall")
        group.material = {"color": (0.4, 0.4, 0.4)}
        scene.groups.append(group)
        scene.select([face, group])

        panel = win.tray.entity_info
        panel.refresh()
        assert panel._material_box.currentText() == "(several)"
        panel._material_box.setCurrentIndex(
            panel._material_box.findData("Brick"))

        assert face.attrs["mat"] == "Brick"
        assert tuple(face.attrs["color"]) == brick.color
        assert face.attrs["opacity"] == 0.8
        assert group.material == brick.face_attrs()

        assert vp.history.undo()
        assert face.attrs["mat"] == "Old"
        assert tuple(face.attrs["color"]) == (0.1, 0.2, 0.3)
        assert "opacity" not in face.attrs
        assert group.material == {"color": (0.4, 0.4, 0.4)}
    finally:
        win._saved_version = scene.version
        win.close()


def test_default_material_clears_front_paint_on_all_selected_entities():
    win = _window()
    vp = win.viewport
    try:
        scene = vp.scene
        mat = Material("Glass", color=(0.5, 0.8, 1.0),
                       texture={"path": "glass.png", "sw": 1, "sh": 1},
                       opacity=0.4)
        scene.materials[mat.name] = mat
        face = _face(scene.mesh)
        face.attrs.update(mat.face_attrs())
        face.attrs["back"] = {"color": (1.0, 0.0, 0.0)}
        group = Group(Mesh(), name="Pane")
        group.material = mat.face_attrs()
        scene.groups.append(group)
        scene.select([face, group])

        panel = win.tray.entity_info
        panel.refresh()
        panel._material_box.setCurrentIndex(
            panel._material_box.findData(""))

        assert not any(k in face.attrs
                       for k in ("mat", "color", "texture", "opacity"))
        assert face.attrs["back"] == {"color": (1.0, 0.0, 0.0)}
        assert group.material is None

        assert vp.history.undo()
        assert face.attrs["mat"] == "Glass"
        assert group.material == mat.face_attrs()
    finally:
        win._saved_version = scene.version
        win.close()


def test_material_field_hides_when_selection_cannot_be_painted():
    win = _window()
    try:
        panel = win.tray.entity_info
        edge = next(iter(_face(win.viewport.scene.mesh).loop[0].edges))
        win.viewport.scene.select([edge])
        panel.refresh()
        assert not panel._material_box.isVisibleTo(panel)
    finally:
        win._saved_version = win.viewport.scene.version
        win.close()
