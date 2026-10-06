# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""History.execute must be transactional: a command that throws mid-mutation
rolls the mesh back to its pre-command state and lands nowhere on the undo
stack. An aborted draw once left a quarter circle, an unsplit face and a
duplicated edge behind (aas.igz), with the traceback swallowed by Qt."""
from __future__ import annotations

from PySide6.QtGui import QVector3D

import core.history as history_module
from core.history import AddEdgeCommand, Command, History, MoveVerticesCommand
from core.scene import Scene


class _ExplodesMidway(Command):
    """Mutates the mesh, then throws — simulating a mid-commit failure."""

    def do(self, scene) -> None:
        scene.mesh.add_edge(QVector3D(0, 0, 0), QVector3D(1, 0, 0))
        scene.mesh.add_edge(QVector3D(1, 0, 0), QVector3D(2, 5, 0))
        raise ValueError("degenerate edge")

    def undo(self, scene) -> None:  # pragma: no cover - never reached
        raise AssertionError("undo of a failed command must never run")


def test_failed_command_rolls_back_and_stays_off_the_undo_stack(tmp_path):
    scene = Scene()
    hist = History(scene)
    hist.error_log = str(tmp_path / "errors.log")
    hist.execute(AddEdgeCommand(QVector3D(5, 5, 0), QVector3D(9, 5, 0)))
    assert len(scene.mesh.edges) == 1

    hist.execute(_ExplodesMidway())
    assert len(scene.mesh.edges) == 1              # partial mutation reverted
    assert len(hist.undo_stack) == 1               # failed cmd not recorded
    assert hist.last_error and "degenerate edge" in hist.last_error
    assert "ValueError" in (tmp_path / "errors.log").read_text()

    # The surviving history still works.
    assert hist.undo()
    assert len(scene.mesh.edges) == 0
    assert hist.redo()
    assert len(scene.mesh.edges) == 1


def test_successful_command_clears_last_error():
    scene = Scene()
    hist = History(scene)
    hist.last_error = "stale"
    hist.execute(AddEdgeCommand(QVector3D(0, 0, 0), QVector3D(1, 1, 0)))
    assert hist.last_error is None


def test_plain_move_reuses_its_snapshot_in_history(monkeypatch):
    scene = Scene()
    scene.mesh.add_face([QVector3D(0, 0, 0), QVector3D(1, 0, 0),
                         QVector3D(0, 1, 0)])
    capture = scene.mesh.capture_state
    calls = []

    def counted_capture():
        calls.append(1)
        return capture()

    monkeypatch.setattr(scene.mesh, "capture_state", counted_capture)
    hist = History(scene)
    hist.execute(MoveVerticesCommand([QVector3D(0, 0, 0)],
                                     QVector3D(0, 0, 1)))
    assert hist.last_error is None
    assert not calls  # no full guard snapshot and no topology snapshots
    assert hist.undo()
    assert scene.mesh.vertex_at(QVector3D(0, 0, 0)) is not None


def test_plain_move_failure_restores_positions_and_registry(monkeypatch, tmp_path):
    scene = Scene()
    mesh = scene.mesh
    mesh.add_face([QVector3D(0, 0, 0), QVector3D(1, 0, 0),
                   QVector3D(0, 1, 0)])
    before = mesh.capture_state()
    move = mesh.move_vertex
    calls = 0

    def fails_on_second_vertex(vertex, delta):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("second vertex failed")
        return move(vertex, delta)

    monkeypatch.setattr(mesh, "move_vertex", fails_on_second_vertex)
    hist = History(scene)
    hist.error_log = str(tmp_path / "errors.log")
    hist.execute(MoveVerticesCommand([QVector3D(0, 0, 0),
                                      QVector3D(1, 0, 0)],
                                     QVector3D(0, 0, 1)))
    assert mesh.capture_state() == before
    assert hist.last_error and "second vertex failed" in hist.last_error
    assert not hist.undo_stack


def test_autofold_failure_restores_topology_with_command_snapshot(
        monkeypatch, tmp_path):
    scene = Scene()
    mesh = scene.mesh
    mesh.add_face([QVector3D(0, 0, 0), QVector3D(2, 0, 0),
                   QVector3D(2, 2, 0), QVector3D(0, 2, 0)])
    before = mesh.capture_state()
    fold = history_module.fold_nonplanar_faces

    def fails_after_fold(*args, **kwargs):
        fold(*args, **kwargs)
        assert len(mesh.faces) > 1  # failure occurs after topology changed
        raise RuntimeError("fold failed")

    monkeypatch.setattr(history_module, "fold_nonplanar_faces", fails_after_fold)
    hist = History(scene)
    hist.error_log = str(tmp_path / "errors.log")
    hist.execute(MoveVerticesCommand([QVector3D(0, 0, 0)],
                                     QVector3D(0, 0, 1)))
    assert mesh.capture_state() == before
    assert hist.last_error and "fold failed" in hist.last_error
    assert not hist.undo_stack


def test_move_preflight_failure_does_not_change_mesh(monkeypatch, tmp_path):
    scene = Scene()
    mesh = scene.mesh
    mesh.add_face([QVector3D(0, 0, 0), QVector3D(2, 0, 0),
                   QVector3D(2, 2, 0), QVector3D(0, 2, 0)])
    before = mesh.capture_state()

    def fails_during_preflight(*_args, **_kwargs):
        raise RuntimeError("preflight failed")

    monkeypatch.setattr(history_module, "is_planar", fails_during_preflight)
    hist = History(scene)
    hist.error_log = str(tmp_path / "errors.log")
    hist.execute(MoveVerticesCommand([QVector3D(0, 0, 0)],
                                     QVector3D(0, 0, 1)))
    assert mesh.capture_state() == before
    assert hist.last_error and "preflight failed" in hist.last_error
    assert not hist.undo_stack
