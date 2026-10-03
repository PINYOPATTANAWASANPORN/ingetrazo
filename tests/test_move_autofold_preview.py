# SPDX-License-Identifier: GPL-3.0-or-later
"""Move shows the fold it will create before changing real topology."""
from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QVector3D

from core.history import History
from core.scene import Scene
from core.topology import _key, is_planar
from tools.base import ToolContext
from tools.move import MoveTool


def V(x, y, z=0.0):
    return QVector3D(float(x), float(y), float(z))


class _Vp:
    def __init__(self, scene, picked_vertex):
        self.scene = scene
        self.history = History(scene)
        self.picked_vertex = picked_vertex

    def update(self):
        pass

    def pick_vertex(self, x, y):
        return QVector3D(self.picked_vertex)

    def pick_group(self, x, y):
        return None

    def pick_edge(self, x, y):
        return None

    def pick_face(self, x, y):
        return None


def _ctx(vp, point):
    return ToolContext(viewport=vp, world=QVector3D(point),
                       screen=QPointF(0, 0), modifiers=Qt.NoModifier,
                       snap=None)


def _square_scene():
    scene = Scene()
    scene.mesh.add_face([V(0, 0), V(2, 0), V(2, 2), V(0, 2)])
    return scene


def test_corner_drag_previews_the_same_single_fold_that_commit_creates():
    scene = _square_scene()
    vp = _Vp(scene, V(2, 2))
    tool = MoveTool()

    tool.on_click(_ctx(vp, V(2, 2)))
    tool.on_hover(_ctx(vp, V(2, 2, 1)))

    assert len(scene.mesh.faces) == 1  # preview never edits real topology
    preview = tool.rubber_band_lines()
    assert len(preview) == 2           # move vector + one predicted fold
    predicted = {_key(p) for p in preview[1]}

    tool.on_click(_ctx(vp, V(2, 2, 1)))
    folds = [edge for edge in scene.mesh.edges if len(edge.faces) == 2]
    assert len(folds) == 1
    assert {_key(folds[0].a), _key(folds[0].b)} == predicted
    assert len(vp.history.undo_stack) == 1

    assert vp.history.undo()
    assert len(scene.mesh.faces) == 1
    assert len(scene.mesh.faces[0].vertices) == 4


def test_in_plane_corner_drag_does_not_preview_or_create_a_fold():
    scene = _square_scene()
    vp = _Vp(scene, V(2, 2))
    tool = MoveTool()

    tool.on_click(_ctx(vp, V(2, 2)))
    tool.on_hover(_ctx(vp, V(3, 3)))
    assert len(tool.rubber_band_lines()) == 1  # move vector only

    tool.on_click(_ctx(vp, V(3, 3)))
    assert len(scene.mesh.faces) == 1
    assert len(scene.mesh.faces[0].vertices) == 4


def test_typed_distance_updates_autofold_and_remains_one_undo_step():
    scene = _square_scene()
    vp = _Vp(scene, V(2, 2))
    tool = MoveTool()

    tool.on_click(_ctx(vp, V(2, 2)))
    tool.on_hover(_ctx(vp, V(2, 2, 1)))  # supplies the typed value direction
    assert tool.on_value(vp, 2.5)

    moved = scene.mesh.vertex_at(V(2, 2, 2.5))
    assert moved is not None
    assert len(scene.mesh.faces) == 2
    assert len(vp.history.undo_stack) == 1
    assert vp.history.undo()
    assert scene.mesh.vertex_at(V(2, 2)) is not None


def test_moving_a_pentagon_edge_previews_folds_and_cancel_restores_it():
    scene = Scene()
    face = scene.mesh.add_face(
        [V(0, 0), V(4, 0), V(4, 4), V(2, 6), V(0, 4)])
    edge = scene.mesh.find_edge(face.loop[2], face.loop[3])
    scene.selection = [edge]
    vp = _Vp(scene, V(4, 4))
    tool = MoveTool()

    tool.on_click(_ctx(vp, V(4, 4)))
    tool.on_hover(_ctx(vp, V(4, 4, 1.5)))
    assert len(scene.mesh.faces) == 1
    assert len(tool.rubber_band_lines()) > 1

    tool.on_cancel(vp)
    assert len(scene.mesh.faces) == 1
    assert all(abs(vertex.z()) < 1e-9 for vertex in face.vertices)
    assert tool.rubber_band_lines() == []
    assert vp.history.undo_stack == []


def test_moving_a_pentagon_edge_commits_only_planar_pieces():
    scene = Scene()
    face = scene.mesh.add_face(
        [V(0, 0), V(4, 0), V(4, 4), V(2, 6), V(0, 4)])
    edge = scene.mesh.find_edge(face.loop[2], face.loop[3])
    scene.selection = [edge]
    vp = _Vp(scene, V(4, 4))
    tool = MoveTool()

    tool.on_click(_ctx(vp, V(4, 4)))
    tool.on_hover(_ctx(vp, V(4, 4, 1.5)))
    predicted = len(tool.rubber_band_lines()) - 1
    tool.on_click(_ctx(vp, V(4, 4, 1.5)))

    assert len(scene.mesh.faces) > 1
    assert all(is_planar(list(piece.vertices)) for piece in scene.mesh.faces)
    assert len([item for item in scene.mesh.edges if len(item.faces) == 2]) == predicted
    assert len(vp.history.undo_stack) == 1
