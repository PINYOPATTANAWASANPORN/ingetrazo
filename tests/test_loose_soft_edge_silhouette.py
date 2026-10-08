"""Loose profile candidates and planes keep the public visibility contract."""
from types import SimpleNamespace

import numpy as np
from PySide6.QtGui import QMatrix4x4, QVector3D as V

from core.history import History, MoveVerticesCommand
from core.layers import Layer, assign_layer
from core.mesh import Mesh
from core.scene import Scene
import views.viewport as viewport_module
from views.viewport import (Viewport, _loose_soft_edge_arrays,
                            _visible_loose_soft_edges)


def _face(mesh, x):
    return mesh.add_face([V(x, 0, 0), V(x + 1, 0, 0), V(x, 1, 0)])


def test_soft_edge_candidates_match_scene_visibility_and_custom_predicate():
    mesh = Mesh()
    faces = [_face(mesh, x) for x in (0, 10, 20, 30)]
    isolated = mesh.add_edge(V(50, 0, 0), V(51, 0, 0))
    for edge in mesh.edges:
        edge.soft = True
    scene = Scene(mesh=mesh)
    scene.layers.extend([Layer("Hidden", visible=False),
                         Layer("Locked", locked=True)])
    for face, tag in zip(faces[1:], ("Hidden", "Locked", "Missing")):
        for edge in mesh.edges:
            if face in edge.faces:
                assign_layer(edge, tag)
    first_edge = next(edge for edge in mesh.edges if faces[0] in edge.faces)
    first_edge.hidden = True
    second_edge = next(edge for edge in mesh.edges
                       if faces[0] in edge.faces and edge is not first_edge)
    second_edge.soft = False

    def reference():
        return [edge for edge in mesh.edges
                if edge.soft and not edge.hidden and edge.faces
                and scene.entity_visible(edge)]

    assert list(_visible_loose_soft_edges(scene)) == reference()
    assert isolated not in reference()
    assert any(faces[2] in edge.faces for edge in reference())  # locked draws
    assert any(faces[3] in edge.faces for edge in reference())  # unknown draws
    assert not any(faces[1] in edge.faces for edge in reference())

    scene.layers.append(Layer("Hidden", visible=True))
    assert list(_visible_loose_soft_edges(scene)) == reference()
    scene.layer("Hidden").visible = True
    assert list(_visible_loose_soft_edges(scene)) == reference()

    original = scene.entity_visible
    seen = []
    scene.entity_visible = lambda edge: (seen.append(edge) or
                                         (original(edge) and edge is not second_edge))
    expected = reference()
    seen.clear()
    assert list(_visible_loose_soft_edges(scene)) == expected
    assert seen == [edge for edge in mesh.edges
                    if edge.soft and not edge.hidden]
    assert isolated in seen


def test_soft_edge_planes_match_original_geometry_for_one_two_many_faces():
    mesh = Mesh()
    first = mesh.add_face([V(0, 0, 0), V(1, 0, 0), V(0, 1, 0)])
    second = mesh.add_face([V(1, 0, 0), V(0, 0, 0), V(0, 0, 1)])
    boundary = next(edge for edge in mesh.edges
                    if first in edge.faces and len(edge.faces) == 1)
    shared = next(edge for edge in mesh.edges if len(edge.faces) == 2)

    def check(edges):
        pts, n0, c0, n1, c1, single = _loose_soft_edge_arrays(edges)
        assert pts.dtype == np.float32
        for i, edge in enumerate(edges):
            np.testing.assert_array_equal(
                pts[i], [edge.a.x(), edge.a.y(), edge.a.z(),
                         edge.b.x(), edge.b.y(), edge.b.z()])
            f0 = np.array([[p.x(), p.y(), p.z()]
                           for p in edge.faces[0].vertices[:3]])
            f1 = np.array([[p.x(), p.y(), p.z()]
                           for p in (edge.faces[1] if len(edge.faces) == 2
                                     else edge.faces[0]).vertices[:3]])
            np.testing.assert_array_equal(c0[i], f0[0])
            np.testing.assert_array_equal(c1[i], f1[0])
            np.testing.assert_array_equal(n0[i], np.cross(f0[1] - f0[0],
                                                          f0[2] - f0[0]))
            np.testing.assert_array_equal(n1[i], np.cross(f1[1] - f1[0],
                                                          f1[2] - f1[0]))
            assert bool(single[i]) == (len(edge.faces) != 2)

    check([boundary, shared])
    mesh.add_face([V(0, 0, 0), V(1, 0, 0), V(0, -1, 0)])
    assert len(shared.faces) == 3
    check([shared])


def test_soft_edge_plane_snapshot_reuses_faces_only_within_one_rebuild():
    class Point:
        def __init__(self, xyz):
            self.xyz = xyz
            self.reads = 0

        def toTuple(self):
            self.reads += 1
            return self.xyz

    class FaceLike:
        def __init__(self):
            self.loop = [SimpleNamespace(position=Point(xyz))
                         for xyz in ((0, 0, 0), (1, 0, 0), (0, 1, 0))]

    face = FaceLike()
    edges = [SimpleNamespace(v0=SimpleNamespace(position=Point((0, 0, 0))),
                             v1=SimpleNamespace(position=Point((1, 0, 0))),
                             faces=[face]) for _ in range(3)]
    first = _loose_soft_edge_arrays(edges)
    assert [v.position.reads for v in face.loop] == [1, 1, 1]
    assert all(np.array_equal(first[1][0], normal) for normal in first[1])

    face.loop[2].position.xyz = (0, 1, 1)
    second = _loose_soft_edge_arrays(edges)
    assert [v.position.reads for v in face.loop] == [2, 2, 2]
    assert not np.array_equal(first[1], second[1])


def test_soft_edge_arrays_are_empty_without_candidates():
    pts, n0, c0, n1, c1, single = _loose_soft_edge_arrays([])
    assert pts.shape == (0, 6) and pts.dtype == np.float32
    assert n0.shape == (0, 3) and n0.dtype == np.float64
    assert c0.shape == (0, 3) and c1.shape == (0, 3)
    assert n1.shape == (0, 3)
    assert single.shape == (0,) and single.dtype == bool


def test_unrelated_move_and_undo_reuse_soft_arrays_but_face_move_rebuilds(monkeypatch):
    mesh = Mesh()
    face = mesh.add_face([V(0, 0, 0), V(2, 0, 0), V(0, 2, 0)])
    soft = mesh.find_edge(face.loop[0], face.loop[1])
    soft.soft = True
    mesh.add_face([V(10, 0, 0), V(12, 0, 0), V(10, 2, 0)])
    scene = Scene(mesh=mesh)
    history = History(scene)

    class Buffer:
        def bind(self):
            pass

        def allocate(self, *_args):
            pass

        def release(self):
            pass

    camera = SimpleNamespace(projection_matrix=QMatrix4x4,
                             view_matrix=QMatrix4x4,
                             eye=lambda: V(0, 0, 10))
    viewport = SimpleNamespace(scene=scene, camera=camera,
                               _silhouette_vbo=Buffer(),
                               _placements_epoch=lambda: 0,
                               _placements=lambda: [], _sil_last=None)
    original = viewport_module._loose_soft_edge_arrays
    calls = []

    def counted(edges):
        calls.append(len(edges))
        return original(edges)

    monkeypatch.setattr(viewport_module, "_loose_soft_edge_arrays", counted)

    def render():
        viewport._sil_last = None  # test the source cache, not frame throttle
        Viewport._upload_silhouette_edges(viewport)
        return viewport._soft_edges_cache[1]

    first = render()
    assert calls == [1]

    remote = MoveVerticesCommand([V(10, 2, 0)], V(0, 0, 1))
    history.execute(remote)
    assert remote._soft_arrays_unchanged
    assert render() is first
    history.undo()
    assert render() is first
    history.redo()
    assert render() is first
    assert calls == [1]

    # A custom visibility predicate may depend on more than the moved mesh;
    # it must take the public filtering path even for a safe Move marker.
    original_visible = scene.entity_visible
    scene.entity_visible = lambda entity: original_visible(entity)
    scene.version += 1
    first = render()
    assert calls == [1, 1]
    custom_move = MoveVerticesCommand([V(10, 2, 1)], V(0, 0, 1))
    history.execute(custom_move)
    assert custom_move._soft_arrays_unchanged
    assert render() is not first
    assert calls == [1, 1, 1]
    del scene.entity_visible

    scene.version += 1  # another edit happened after the Move
    first = render()
    assert calls == [1, 1, 1, 1]

    # The moved vertex is not an endpoint of the soft edge, but it changes
    # that edge's Face plane and must invalidate the arrays.
    plane_edit = MoveVerticesCommand([V(0, 2, 0)], V(0, 0, 1))
    history.execute(plane_edit)
    assert not plane_edit._soft_arrays_unchanged
    changed = render()
    assert changed is not first and calls == [1, 1, 1, 1, 1]
    assert not np.array_equal(changed[1], first[1])
