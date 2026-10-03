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

    def _segment_to_pixels(self, a, b):
        return ((a.x(), a.y()), (b.x(), b.y()))

    def _world_to_pixel(self, point):
        return (point.x(), point.y())


class _Painter:
    def __init__(self):
        self.lines = []
        self.texts = []

    def setPen(self, pen):
        pass

    def setFont(self, font):
        pass

    def drawLine(self, a, b):
        self.lines.append((a, b))

    def drawText(self, point, text):
        self.texts.append(text)


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
    assert len(tool.rubber_band_lines()) == 1  # move vector keeps snap colour
    preview = tool.autofold_preview_lines()
    assert len(preview) == 1           # topology gets its own visual channel
    assert tool._fold_face_count == 1
    predicted = {_key(p) for p in preview[0]}

    tool.on_click(_ctx(vp, V(2, 2, 1)))
    folds = [edge for edge in scene.mesh.edges if len(edge.faces) == 2]
    assert len(folds) == 1
    assert {_key(folds[0].a), _key(folds[0].b)} == predicted
    assert len(vp.history.undo_stack) == 1

    assert vp.history.undo()
    assert len(scene.mesh.faces) == 1
    assert len(scene.mesh.faces[0].vertices) == 4


def test_autofold_overlay_draws_distinct_dashed_edge_and_consequence_label():
    scene = _square_scene()
    vp = _Vp(scene, V(2, 2))
    tool = MoveTool()

    tool.on_click(_ctx(vp, V(2, 2)))
    tool.on_hover(_ctx(vp, V(2, 2, 1)))
    painter = _Painter()
    tool.draw_overlay(vp, painter)

    # Each predicted fold gets a white halo and a violet dashed stroke.
    assert len(painter.lines) == 2
    # The same two-pass treatment keeps the label legible on any model.
    assert len(painter.texts) == 2
    assert painter.texts[0] == painter.texts[1]
    assert "Autofold" in painter.texts[0]
    assert "1" in painter.texts[0]


def test_in_plane_corner_drag_does_not_preview_or_create_a_fold():
    scene = _square_scene()
    vp = _Vp(scene, V(2, 2))
    tool = MoveTool()

    tool.on_click(_ctx(vp, V(2, 2)))
    tool.on_hover(_ctx(vp, V(3, 3)))
    assert len(tool.rubber_band_lines()) == 1  # move vector only
    assert tool.autofold_preview_lines() == []
    assert tool._fold_face_count == 0

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
    assert len(tool.rubber_band_lines()) == 1
    assert tool.autofold_preview_lines()
    assert tool._fold_face_count == 1

    tool.on_cancel(vp)
    assert len(scene.mesh.faces) == 1
    assert all(abs(vertex.z()) < 1e-9 for vertex in face.vertices)
    assert tool.rubber_band_lines() == []
    assert tool.autofold_preview_lines() == []
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
    predicted = len(tool.autofold_preview_lines())
    tool.on_click(_ctx(vp, V(4, 4, 1.5)))

    assert len(scene.mesh.faces) > 1
    assert all(is_planar(list(piece.vertices)) for piece in scene.mesh.faces)
    assert len([item for item in scene.mesh.edges if len(item.faces) == 2]) == predicted
    assert len(vp.history.undo_stack) == 1
