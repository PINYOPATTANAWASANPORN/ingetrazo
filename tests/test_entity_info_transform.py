# SPDX-License-Identifier: GPL-3.0-or-later
"""Entity Info edits position and size of whole-object selections."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtGui import QMatrix4x4, QVector3D
from PySide6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication([])

from core.group import Group
from core.mesh import Mesh


def V(x, y, z=0.0):
    return QVector3D(float(x), float(y), float(z))


def _group(name, x0=0.0):
    mesh = Mesh()
    mesh.add_face([V(x0, 0), V(x0 + 1, 0),
                   V(x0 + 1, 1), V(x0, 1)])
    return Group(mesh, name=name)


def _window():
    from views.main_window import MainWindow
    win = MainWindow()
    win.viewport.scene.units = {"length": "m", "precision": 3}
    win.show()
    _app.processEvents()
    return win


def _centre_and_size(scene):
    lo, hi = scene.selection_bounds()
    return (lo + hi) * 0.5, hi - lo


def test_multi_object_position_moves_everything_as_one_undo_step():
    win = _window()
    vp = win.viewport
    try:
        scene = vp.scene
        a, b = _group("A", 0), _group("B", 3)
        scene.groups.extend([a, b])
        scene.select([a, b])
        panel = win.tray.entity_info
        panel.refresh()

        assert panel._transform_box.isVisibleTo(panel)
        assert panel._position_spins[0].value() == pytest.approx(2.0)
        assert panel._position_spins[0].locale().name() == "C"
        panel._position_spins[0].setValue(7.0)
        panel._on_position_edited(0)

        centre, size = _centre_and_size(scene)
        assert centre.x() == pytest.approx(7.0)
        assert size.x() == pytest.approx(4.0)
        assert vp.history.undo()
        centre, _size = _centre_and_size(scene)
        assert centre.x() == pytest.approx(2.0)
    finally:
        win._saved_version = scene.version
        win.close()


def test_multi_object_size_scales_geometry_and_spacing_then_undoes():
    win = _window()
    vp = win.viewport
    try:
        scene = vp.scene
        a, b = _group("A", 0), _group("B", 3)
        scene.groups.extend([a, b])
        scene.select([a, b])
        panel = win.tray.entity_info
        panel.refresh()

        assert panel._size_spins[0].value() == pytest.approx(4.0)
        panel._size_spins[0].setValue(8.0)
        panel._on_size_edited(0)

        centre, size = _centre_and_size(scene)
        assert centre.x() == pytest.approx(2.0)
        assert size.x() == pytest.approx(8.0)
        assert vp.history.undo()
        centre, size = _centre_and_size(scene)
        assert centre.x() == pytest.approx(2.0)
        assert size.x() == pytest.approx(4.0)
    finally:
        win._saved_version = scene.version
        win.close()


def test_component_instance_position_changes_placement_not_shared_mesh():
    win = _window()
    vp = win.viewport
    try:
        scene = vp.scene
        component = _group("Component")
        prototype_state = component.mesh.capture_state()
        component.xform = QMatrix4x4()
        component.xform.translate(10, 0, 0)
        scene.groups.append(component)
        scene.select([component])
        panel = win.tray.entity_info
        panel.refresh()

        panel._position_spins[1].setValue(5.0)
        panel._on_position_edited(1)
        centre, _size = _centre_and_size(scene)
        assert centre.y() == pytest.approx(5.0)
        assert component.mesh.capture_state() == prototype_state
        assert vp.history.undo()
        centre, _size = _centre_and_size(scene)
        assert centre.y() == pytest.approx(0.5)
    finally:
        win._saved_version = scene.version
        win.close()


def test_transform_fields_hide_for_mixed_face_and_object_selection():
    win = _window()
    try:
        scene = win.viewport.scene
        group = _group("A")
        face = scene.mesh.add_face([V(3, 0), V(4, 0), V(4, 1), V(3, 1)])
        scene.groups.append(group)
        scene.select([group, face])
        panel = win.tray.entity_info
        panel.refresh()
        assert not panel._transform_box.isVisibleTo(panel)
    finally:
        win._saved_version = scene.version
        win.close()
