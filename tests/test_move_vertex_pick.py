from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QVector3D

from core.scene import Scene
from tools.base import ToolContext
from tools.move import gather_targets


def V(x, y, z=0.0):
    return QVector3D(x, y, z)


class _Viewport:
    def __init__(self, scene, point, edge):
        self.scene = scene
        self._point = point
        self._edge = edge

    def pick_vertex(self, _x, _y):
        return self._point

    def pick_group(self, _x, _y):
        return None

    def pick_edge(self, _x, _y):
        return self._edge

    def pick_face(self, _x, _y):
        return None


def _ctx(viewport):
    return ToolContext(viewport=viewport, world=V(0, 0),
                       screen=QPointF(0, 0), modifiers=Qt.NoModifier,
                       snap=None)


def test_move_prefers_one_loose_vertex_over_the_edge_beneath_it():
    scene = Scene()
    edge = scene.mesh.add_edge(V(0, 0), V(2, 0))
    viewport = _Viewport(scene, V(0, 0), edge)

    groups, positions = gather_targets(_ctx(viewport), prefer_vertex=True)

    assert groups == []
    assert positions == [V(0, 0)]


def test_other_transform_tools_and_selected_edges_keep_whole_edge_behavior():
    scene = Scene()
    edge = scene.mesh.add_edge(V(0, 0), V(2, 0))
    viewport = _Viewport(scene, V(0, 0), edge)

    _groups, positions = gather_targets(_ctx(viewport))
    assert positions == [V(0, 0), V(2, 0)]

    scene.selection.add(edge)
    _groups, positions = gather_targets(_ctx(viewport), prefer_vertex=True)
    assert positions == [V(0, 0), V(2, 0)]
