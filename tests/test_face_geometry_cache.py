"""Viewport geometry memo survives unrelated edits without stale triangles."""
from __future__ import annotations

from PySide6.QtGui import QVector3D

from core.mesh import Face, Mesh
from core.history import History, MoveVerticesCommand
from core.scene import Scene
from views.viewport import Viewport
import views.viewport as viewport_module


def _view(scene):
    class Stub:
        pass

    view = Stub()
    view.scene = scene
    for name in ("_newell_of", "_normal_of", "_tris_of"):
        setattr(view, name, getattr(Viewport, name).__get__(view))
    return view


def _triangle(mesh, x):
    mesh.add_face([QVector3D(x, 0, 0), QVector3D(x + 1, 0, 0),
                   QVector3D(x, 1, 0)])
    return mesh.faces[-1]


def test_unrelated_move_keeps_face_triangulation(monkeypatch):
    mesh = Mesh()
    edited = _triangle(mesh, 0)
    untouched = _triangle(mesh, 10)
    scene = Scene(mesh=mesh)
    view = _view(scene)
    original = Face.triangulate
    calls = {edited: 0, untouched: 0}

    def counted(face, normal=None):
        calls[face] += 1
        return original(face, normal)

    monkeypatch.setattr(Face, "triangulate", counted)
    before_untouched = view._tris_of(untouched)
    before_edited = view._tris_of(edited)
    mesh.move_vertex(edited.loop[0], QVector3D(0, 0, 1))
    scene.version += 1
    assert view._tris_of(untouched) is before_untouched
    assert view._tris_of(edited) is not before_edited
    assert calls == {edited: 2, untouched: 1}


def test_hole_and_loop_changes_invalidate_geometry_cache(monkeypatch):
    mesh = Mesh()
    face = _triangle(mesh, 0)
    scene = Scene(mesh=mesh)
    view = _view(scene)
    original = Face.triangulate
    calls = 0

    def counted(current, normal=None):
        nonlocal calls
        calls += 1
        return original(current, normal)

    monkeypatch.setattr(Face, "triangulate", counted)
    view._tris_of(face)
    scene.version += 1
    view._tris_of(face)
    assert calls == 1
    face.loop = [face.loop[1], face.loop[2], face.loop[0]]
    scene.version += 1
    view._tris_of(face)
    assert calls == 2
    # The signature includes holes even when their outer loop stays put.
    face.hole_loops = [[mesh.vertex(QVector3D(.1, .1, 0)),
                        mesh.vertex(QVector3D(.2, .1, 0)),
                        mesh.vertex(QVector3D(.1, .2, 0))]]
    scene.version += 1
    view._tris_of(face)
    assert calls == 3


def test_move_undo_redo_refreshes_face_geometry():
    mesh = Mesh()
    face = _triangle(mesh, 0)
    scene = Scene(mesh=mesh)
    view = _view(scene)
    history = History(scene)

    def heights():
        return sorted(p.z() for tri in view._tris_of(face) for p in tri)

    assert heights() == [0, 0, 0]
    history.execute(MoveVerticesCommand([QVector3D(0, 0, 0)],
                                        QVector3D(0, 0, 1)))
    assert heights() == [0, 0, 1]
    assert history.undo()
    assert heights() == [0, 0, 0]
    assert history.redo()
    assert heights() == [0, 0, 1]


def test_large_active_mesh_does_not_keep_persistent_face_cache(monkeypatch):
    mesh = Mesh()
    face = _triangle(mesh, 0)
    _triangle(mesh, 10)
    view = _view(Scene(mesh=mesh))
    monkeypatch.setattr(viewport_module, "_PERSISTENT_FACE_LIMIT", 1)
    view._tris_of(face)
    assert face._render_geom_cache is None
