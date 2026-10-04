# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""New groups and components belong to the active tag."""
from __future__ import annotations

from PySide6.QtGui import QVector3D

from core.group import Group
from core.history import (GroupToComponentCommand, History, MakeComponentOfCommand,
                          MakeGroupCommand, MakeNestedGroupCommand)
from core.layers import Layer, layer_of
from core.mesh import Mesh
from core.scene import Scene


def _scene_with_face():
    scene = Scene()
    scene.layers.append(Layer("Structure"))
    scene.set_active_layer("Structure")
    face = scene.mesh.add_face([
        QVector3D(0, 0, 0), QVector3D(2, 0, 0),
        QVector3D(2, 1, 0), QVector3D(0, 1, 0),
    ])
    return scene, face


def test_make_group_uses_active_layer_and_redo_keeps_it():
    scene, face = _scene_with_face()
    history = History(scene)
    command = MakeGroupCommand([face], [])

    history.execute(command)
    assert layer_of(command.group) == "Structure"

    history.undo()
    scene.set_active_layer("Layer 0")
    history.redo()
    assert layer_of(command.group) == "Structure"


def test_make_component_from_loose_geometry_uses_active_layer():
    scene, face = _scene_with_face()
    command = MakeGroupCommand([face], [], component=True, name="Panel")

    History(scene).execute(command)

    assert command.group.is_component()
    assert layer_of(command.group) == "Structure"


def test_nested_group_and_component_use_active_layer():
    scene = Scene()
    scene.layers.append(Layer("Furniture"))
    scene.set_active_layer("Furniture")
    first = Group(Mesh(), name="Chair")
    second = Group(Mesh(), name="Table")
    scene.groups.extend([first, second])

    group_command = MakeNestedGroupCommand([], [], [first, second])
    History(scene).execute(group_command)
    assert layer_of(group_command.container) == "Furniture"

    # The component path uses the same newly-created container rule.
    other_scene = Scene()
    other_scene.layers.append(Layer("Furniture"))
    other_scene.set_active_layer("Furniture")
    a = Group(Mesh(), name="A")
    b = Group(Mesh(), name="B")
    other_scene.groups.extend([a, b])
    component_command = MakeComponentOfCommand([], [], [a, b], name="Set")
    History(other_scene).execute(component_command)
    assert component_command.container.is_component()
    assert layer_of(component_command.container) == "Furniture"


def test_converting_existing_group_preserves_its_layer():
    scene = Scene()
    scene.layers.extend([Layer("Existing"), Layer("Active")])
    scene.set_active_layer("Active")
    group = Group(Mesh(), name="Cabinet")
    group.layer = "Existing"
    scene.groups.append(group)

    History(scene).execute(GroupToComponentCommand(group))

    assert group.is_component()
    assert layer_of(group) == "Existing"
