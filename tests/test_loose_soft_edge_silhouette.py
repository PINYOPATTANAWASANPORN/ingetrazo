"""Loose profile candidates and planes keep the public visibility contract."""
import numpy as np
from PySide6.QtGui import QVector3D as V

from core.layers import Layer, assign_layer
from core.mesh import Mesh
from core.scene import Scene
from views.viewport import _loose_soft_edge_arrays, _visible_loose_soft_edges


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
