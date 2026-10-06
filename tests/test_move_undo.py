# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Move undo/redo exactness: moving geometry onto another vertex's position and
undoing must not drag the innocent coincident vertex along (snapshot restore)."""
from __future__ import annotations

from PySide6.QtGui import QVector3D

from core.edits import build_add_edges
from core.history import History, MoveVerticesCommand
from core.scene import Scene


def V(x, y):
    return QVector3D(x, y, 0)


def _positions(scene):
    return sorted((round(v.position.x(), 4), round(v.position.y(), 4))
                  for v in scene.mesh.vertices)


def _two_squares(scene, hist):
    a = [V(0, 0), V(2, 0), V(2, 2), V(0, 2)]
    b = [V(5, 0), V(7, 0), V(7, 2), V(5, 2)]
    for sq in (a, b):
        hist.execute(build_add_edges(
            scene, [(sq[i], sq[(i + 1) % 4]) for i in range(4)],
            detect_faces=True))


def test_move_onto_other_vertex_then_undo_is_exact():
    # Square A moved so two corners land exactly on square B's corners (what an
    # endpoint snap produces). Undo used to translate BY POSITION, dragging B's
    # never-moved corners along — warping the drawing. Must restore exactly.
    scene = Scene()
    hist = History(scene)
    _two_squares(scene, hist)
    before = _positions(scene)
    hist.execute(MoveVerticesCommand(
        [V(0, 0), V(2, 0), V(2, 2), V(0, 2)], QVector3D(3, 0, 0)))
    hist.undo()
    assert _positions(scene) == before


def test_move_undo_redo_cycle_stable():
    scene = Scene()
    hist = History(scene)
    _two_squares(scene, hist)
    before = _positions(scene)
    hist.execute(MoveVerticesCommand(
        [V(0, 0), V(2, 0), V(2, 2), V(0, 2)], QVector3D(3, 0, 0)))
    moved = _positions(scene)
    hist.undo()
    hist.redo()
    assert _positions(scene) == moved      # redo reproduces the move
    hist.undo()
    assert _positions(scene) == before     # and undo is still exact


def test_plain_move_still_works():
    scene = Scene()
    hist = History(scene)
    _two_squares(scene, hist)
    hist.execute(MoveVerticesCommand(
        [V(0, 0), V(2, 0), V(2, 2), V(0, 2)], QVector3D(0, 10, 0)))
    assert (0.0, 10.0) in _positions(scene)
    hist.undo()
    assert (0.0, 0.0) in _positions(scene)


def test_plain_move_uses_position_snapshot_and_restores_registry_collision():
    scene = Scene()
    hist = History(scene)
    _two_squares(scene, hist)
    source = scene.mesh.vertex_at(V(0, 0))
    stationary = scene.mesh.vertex_at(V(5, 0))
    before = scene.mesh.capture_state()
    command = MoveVerticesCommand([V(0, 0)], QVector3D(5, 0, 0))
    hist.execute(command)
    assert command._position_only
    assert source.position == V(5, 0)
    assert stationary.position == V(5, 0)
    after = scene.mesh.capture_state()
    hist.undo()
    assert scene.mesh.capture_state() == before
    assert scene.mesh.vertex_at(V(0, 0)) is source
    assert scene.mesh.vertex_at(V(5, 0)) is stationary
    hist.redo()
    assert scene.mesh.capture_state() == after
    assert source.position == stationary.position
    hist.undo()
    assert scene.mesh.capture_state() == before
    assert scene.mesh.vertex_at(V(0, 0)) is source
    assert scene.mesh.vertex_at(V(5, 0)) is stationary


def test_warping_move_keeps_full_topology_snapshot():
    scene = Scene()
    hist = History(scene)
    corners = [QVector3D(0, 0, 0), QVector3D(2, 0, 0),
               QVector3D(2, 2, 0), QVector3D(0, 2, 0)]
    face = scene.mesh.add_face(corners)
    original_faces = list(scene.mesh.faces)
    command = MoveVerticesCommand([corners[0]], QVector3D(0, 0, 1))
    hist.execute(command)
    assert not command._position_only
    assert len(scene.mesh.faces) > 1
    hist.undo()
    assert scene.mesh.faces == original_faces
    assert scene.mesh.faces[0] is face
    hist.redo()
    assert len(scene.mesh.faces) > 1


def test_broad_plain_move_keeps_full_snapshot_without_projection_sweep():
    scene = Scene()
    positions = []
    for i in range(257):
        x = float(i * 4)
        positions.append(QVector3D(x, 0, 0))
        scene.mesh.add_face([QVector3D(x, 0, 0),
                             QVector3D(x + 1, 0, 0),
                             QVector3D(x, 1, 0)])
    command = MoveVerticesCommand(positions, QVector3D(0, 0, 1))
    command.do(scene)
    assert not command._position_only
    command.undo(scene)
    assert all(scene.mesh.vertex_at(p) is not None for p in positions)
