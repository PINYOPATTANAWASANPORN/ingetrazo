"""Viewport geometry memo survives unrelated edits without stale triangles."""
from __future__ import annotations

from PySide6.QtGui import QVector3D

from core.mesh import Face, Mesh
from core.history import HideCommand, History, MoveVerticesCommand
from core.layers import Layer, assign_layer
from core.scene import Scene
from views.viewport import Viewport
import views.viewport as viewport_module


def _view(scene):
    class Stub:
        pass

    view = Stub()
    view.scene = scene
    for name in ("_newell_of", "_normal_of", "_tris_of",
                 "_shade_factor", "_shaded_color", "_vcol_face_block",
                 "_dback_face_block", "_visible_loose_faces"):
        setattr(view, name, getattr(Viewport, name).__get__(view))
    view._LIGHT = Viewport._LIGHT
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


def test_signature_checked_once_per_face_and_scene_version(monkeypatch):
    mesh = Mesh()
    face = _triangle(mesh, 0)
    scene = Scene(mesh=mesh)
    view = _view(scene)
    original = viewport_module._face_geometry_signature
    calls = 0

    def counted(current):
        nonlocal calls
        calls += 1
        return original(current)

    monkeypatch.setattr(viewport_module, "_face_geometry_signature", counted)
    view._normal_of(face)
    view._tris_of(face)
    assert calls == 1
    scene.version += 1
    view._normal_of(face)
    view._tris_of(face)
    assert calls == 2


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


def test_signature_detects_in_place_vertex_and_hole_position_changes():
    mesh = Mesh()
    face = _triangle(mesh, 0)
    face.hole_loops = [[mesh.vertex(QVector3D(.1, .1, 0)),
                        mesh.vertex(QVector3D(.2, .1, 0)),
                        mesh.vertex(QVector3D(.1, .2, 0))]]
    original = viewport_module._face_geometry_signature(face)
    face.loop[0].position.setZ(.25)
    changed_outer = viewport_module._face_geometry_signature(face)
    assert changed_outer != original
    face.hole_loops[0][0].position.setZ(.125)
    assert viewport_module._face_geometry_signature(face) != changed_outer


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


def test_packed_face_colour_reuses_only_matching_geometry_and_paint():
    mesh = Mesh()
    edited = _triangle(mesh, 0)
    untouched = _triangle(mesh, 10)
    scene = Scene(mesh=mesh)
    view = _view(scene)
    history = History(scene)
    base = (0.8, 0.5, 0.2)
    before = view._vcol_face_block(untouched, base)
    edited_before = view._vcol_face_block(edited, base)
    back_before = view._dback_face_block(untouched)
    edited_back_before = view._dback_face_block(edited)

    history.execute(MoveVerticesCommand([QVector3D(0, 0, 0)],
                                        QVector3D(0, 0, 1)))
    assert view._vcol_face_block(untouched, base) is before
    assert view._dback_face_block(untouched) is back_before
    assert view._vcol_face_block(edited, base) != edited_before
    assert view._dback_face_block(edited) != edited_back_before
    recoloured = view._vcol_face_block(untouched, (0.2, 0.5, 0.8))
    assert recoloured != before
    assert view._vcol_face_block(untouched, base) == before
    assert history.undo()
    assert view._vcol_face_block(edited, base) == edited_before
    assert view._dback_face_block(edited) == edited_back_before
    assert history.redo()
    assert view._vcol_face_block(edited, base) != edited_before
    assert view._dback_face_block(edited) != edited_back_before


def test_packed_face_colour_cache_respects_cap_and_mesh_switch(monkeypatch):
    mesh = Mesh()
    old_face = _triangle(mesh, 0)
    scene = Scene(mesh=mesh)
    view = _view(scene)
    view._vcol_face_block(old_face, (1, 1, 1))
    view._dback_face_block(old_face)
    assert old_face._render_vcol_cache is not None
    assert old_face._render_dback_cache is not None

    second = Mesh()
    next_face = _triangle(second, 10)
    scene.mesh = second
    scene.version += 1
    view._vcol_face_block(next_face, (1, 1, 1))
    view._dback_face_block(next_face)
    assert old_face._render_vcol_cache is None
    assert old_face._render_dback_cache is None

    monkeypatch.setattr(viewport_module, "_PERSISTENT_FACE_LIMIT", 0)
    scene.version += 1
    view._vcol_face_block(next_face, (1, 1, 1))
    view._dback_face_block(next_face)
    assert next_face._render_vcol_cache is None
    assert next_face._render_dback_cache is None


def test_loose_face_visibility_matches_tags_hide_and_custom_predicate():
    mesh = Mesh()
    visible = _triangle(mesh, 0)
    hidden = _triangle(mesh, 10)
    unknown_tag = _triangle(mesh, 20)
    locked_tag = _triangle(mesh, 30)
    scene = Scene(mesh=mesh)
    view = _view(scene)
    scene.layers.extend([Layer("Hidden", visible=False),
                         Layer("Locked", locked=True)])
    assign_layer(hidden, "Hidden")
    assign_layer(unknown_tag, "Missing")
    assign_layer(locked_tag, "Locked")
    assert list(view._visible_loose_faces()) == [visible, unknown_tag,
                                                  locked_tag]

    scene.layer("Hidden").visible = True
    hidden.attrs["hidden"] = True
    assert list(view._visible_loose_faces()) == [visible, unknown_tag,
                                                  locked_tag]
    hidden.attrs.pop("hidden")
    assert list(view._visible_loose_faces()) == list(mesh.faces)
    scene.layers.append(Layer("Hidden", visible=False))
    assert list(view._visible_loose_faces()) == list(mesh.faces)

    history = History(scene)
    history.execute(HideCommand([visible]))
    assert list(view._visible_loose_faces()) == [hidden, unknown_tag,
                                                  locked_tag]
    assert history.undo()
    assert list(view._visible_loose_faces()) == list(mesh.faces)

    calls = []
    original = scene.entity_visible
    scene.entity_visible = lambda face: (calls.append(face) or original(face))
    assert list(view._visible_loose_faces()) == list(mesh.faces)
    assert calls == list(mesh.faces)


def test_large_active_mesh_does_not_keep_persistent_face_cache(monkeypatch):
    mesh = Mesh()
    face = _triangle(mesh, 0)
    _triangle(mesh, 10)
    view = _view(Scene(mesh=mesh))
    monkeypatch.setattr(viewport_module, "_PERSISTENT_FACE_LIMIT", 1)
    view._tris_of(face)
    assert face._render_geom_cache is None


def test_crossing_limit_releases_existing_face_entries(monkeypatch):
    mesh = Mesh()
    face = _triangle(mesh, 0)
    scene = Scene(mesh=mesh)
    view = _view(scene)
    monkeypatch.setattr(viewport_module, "_PERSISTENT_FACE_LIMIT", 1)
    view._tris_of(face)
    assert face._render_geom_cache is not None
    _triangle(mesh, 10)
    scene.version += 1
    view._tris_of(face)
    assert face._render_geom_cache is None


def test_switching_active_mesh_releases_former_face_entries():
    first = Mesh()
    old_face = _triangle(first, 0)
    scene = Scene(mesh=first)
    view = _view(scene)
    view._tris_of(old_face)
    assert old_face._render_geom_cache is not None
    second = Mesh()
    new_face = _triangle(second, 10)
    scene.mesh = second
    scene.version += 1
    view._tris_of(new_face)
    assert old_face._render_geom_cache is None
    assert new_face._render_geom_cache is not None
