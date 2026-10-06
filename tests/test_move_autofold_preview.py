# SPDX-License-Identifier: GPL-3.0-or-later
"""Move shows the fold it will create before changing real topology."""
from __future__ import annotations

import pytest

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


def test_shared_grid_vertex_folds_all_incident_faces_and_round_trips():
    """One lift must fold four neighboring quads without losing any face."""
    scene = Scene()
    for y in range(3):
        for x in range(3):
            face = scene.mesh.add_face([
                V(x, y), V(x + 1, y), V(x + 1, y + 1), V(x, y + 1)])
            face.attrs["material"] = f"tile-{x}-{y}"
    original_edges = {
        tuple(sorted((_key(edge.a), _key(edge.b))))
        for edge in scene.mesh.edges}
    moved_original_edges = {
        tuple(sorted(_key(V(1, 1, 0.75)) if point == _key(V(1, 1))
                     else point for point in edge))
        for edge in original_edges}
    vp = _Vp(scene, V(1, 1))
    tool = MoveTool()

    tool.on_click(_ctx(vp, V(1, 1)))
    tool.on_hover(_ctx(vp, V(1, 1, 0.75)))
    assert len(scene.mesh.faces) == 9  # preview does not split topology
    predicted = {tuple(sorted((_key(a), _key(b))))
                 for a, b in tool.autofold_preview_lines()}
    assert len(predicted) == 4
    assert tool._fold_face_count == 4

    tool.on_click(_ctx(vp, V(1, 1, 0.75)))
    assert len(scene.mesh.faces) == 13
    assert all(is_planar(list(face.vertices)) for face in scene.mesh.faces)
    assert max(len(edge.faces) for edge in scene.mesh.edges) == 2
    actual = {tuple(sorted((_key(edge.a), _key(edge.b))))
              for edge in scene.mesh.edges if len(edge.faces) == 2
              and tuple(sorted((_key(edge.a), _key(edge.b))))
              not in moved_original_edges}
    assert actual == predicted
    counts = {}
    for face in scene.mesh.faces:
        material = face.attrs["material"]
        counts[material] = counts.get(material, 0) + 1
    assert sorted(counts.values()) == [1] * 5 + [2] * 4

    assert len(vp.history.undo_stack) == 1
    assert vp.history.undo()
    assert len(scene.mesh.faces) == 9
    assert scene.mesh.vertex_at(V(1, 1)) is not None
    assert vp.history.redo()
    assert len(scene.mesh.faces) == 13
    assert scene.mesh.vertex_at(V(1, 1, 0.75)) is not None


@pytest.mark.parametrize("corner", [(4, 4), (3, 3)])
def test_holed_face_autofold_preserves_opening_and_undo(corner):
    """Folding an outer or hole corner must not fill the wall's window."""
    scene = Scene()
    face = scene.mesh.add_face(
        [V(0, 0), V(4, 0), V(4, 4), V(0, 4)],
        [[V(1, 1), V(3, 1), V(3, 3), V(1, 3)]],
    )
    face.attrs["material"] = "wall"
    source = V(*corner)
    destination = V(*corner, 1)
    vp = _Vp(scene, source)
    tool = MoveTool()

    tool.on_click(_ctx(vp, source))
    tool.on_hover(_ctx(vp, destination))
    assert len(scene.mesh.faces) == 1
    assert tool.autofold_preview_lines()
    tool.on_click(_ctx(vp, destination))

    assert len(scene.mesh.faces) > 1
    assert all(is_planar(list(piece.vertices) + [v for h in piece.holes for v in h])
               for piece in scene.mesh.faces)
    assert all(piece.attrs["material"] == "wall" for piece in scene.mesh.faces)
    # The XY projection stays a 4x4 wall minus the 2x2 window, even when
    # Autofold replaces the original holed face with planar pieces.
    projected_area = sum(
        abs((b.x() - a.x()) * (c.y() - a.y())
            - (b.y() - a.y()) * (c.x() - a.x())) / 2
        for piece in scene.mesh.faces for a, b, c in piece.triangulate()
    )
    assert abs(projected_area - 12.0) < 1e-6
    assert len(vp.history.undo_stack) == 1
    assert vp.history.undo()
    assert len(scene.mesh.faces) == 1
    assert len(scene.mesh.faces[0].holes) == 1
    assert vp.history.redo()
    assert len(scene.mesh.faces) > 1


def test_nonmanifold_shared_edge_folds_all_three_incident_faces():
    """Three faces on one edge must keep their radial connection after Move."""
    scene = Scene()
    boundaries = [
        [V(0, 0), V(2, 0), V(2, 2), V(0, 2)],
        [V(2, 0), V(0, 0), V(0, -2), V(2, -2)],
        [V(0, 0), V(2, 0), V(2, 1, 2), V(0, 1, 2)],
    ]
    for index, boundary in enumerate(boundaries):
        face = scene.mesh.add_face(boundary)
        face.attrs["material"] = f"side-{index}"
    vp = _Vp(scene, V(0, 0))
    tool = MoveTool()

    tool.on_click(_ctx(vp, V(0, 0)))
    tool.on_hover(_ctx(vp, V(0, 0, 0.75)))
    assert len(scene.mesh.faces) == 3
    assert tool._fold_face_count == 3
    assert len(tool.autofold_preview_lines()) == 3
    tool.on_click(_ctx(vp, V(0, 0, 0.75)))

    assert len(scene.mesh.faces) == 6
    assert all(is_planar(list(piece.vertices)) for piece in scene.mesh.faces)
    shared = scene.mesh.find_edge(
        scene.mesh.vertex_at(V(0, 0, 0.75)), scene.mesh.vertex_at(V(2, 0)))
    assert shared is not None and len(shared.faces) == 3
    assert sorted(piece.attrs["material"] for piece in scene.mesh.faces) == [
        "side-0", "side-0", "side-1", "side-1", "side-2", "side-2"]
    assert len(vp.history.undo_stack) == 1
    assert vp.history.undo()
    assert len(scene.mesh.faces) == 3
    assert vp.history.redo()
    assert len(scene.mesh.faces) == 6


def test_move_folds_only_incident_faces_shown_by_preview():
    """An unrelated warped face must not change when another corner moves."""
    scene = _square_scene()
    remote = scene.mesh.add_face([
        V(10, 0), V(12, 0), V(12, 2, 1), V(10, 2)])
    assert not is_planar(list(remote.vertices))
    vp = _Vp(scene, V(2, 2))
    tool = MoveTool()

    tool.on_click(_ctx(vp, V(2, 2)))
    tool.on_hover(_ctx(vp, V(2, 2, 1)))
    assert tool._fold_face_count == 1
    assert len(tool.autofold_preview_lines()) == 1
    tool.on_click(_ctx(vp, V(2, 2, 1)))

    assert len(scene.mesh.faces) == 3
    assert remote in scene.mesh.faces
    assert len(remote.vertices) == 4
    assert len(vp.history.undo_stack) == 1
    assert vp.history.undo()
    assert len(scene.mesh.faces) == 2
    assert remote in scene.mesh.faces
    assert vp.history.redo()
    assert len(scene.mesh.faces) == 3
    assert remote in scene.mesh.faces
