# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Alt+click reaches objects hidden below the ordinary front-most pick."""
from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QVector3D

from core.geometry import Face
from core.scene import Scene
from tools.base import ToolContext
from tools.select import SelectTool
from views.viewport import Viewport


def V(x, y, z=0.0):
    return QVector3D(float(x), float(y), float(z))


class _StackedViewport:
    def __init__(self):
        self.scene = Scene()
        self.front = Face([V(0, 0, 1), V(1, 0, 1), V(1, 1, 1)])
        self.back = Face([V(0, 0, 0), V(1, 0, 0), V(1, 1, 0)])
        self.scene.faces.extend((self.front, self.back))
        self.updated = 0

    def pick_group(self, _x, _y):
        return None

    def pick_edge(self, _x, _y):
        return None

    def pick_dimension(self, _x, _y):
        return None

    def pick_geopath(self, _x, _y):
        return None

    def pick_face(self, _x, _y):
        return self.front

    def pick_selection_candidates(self, _x, _y):
        return [self.front, self.back]

    def update(self):
        self.updated += 1


def _click(viewport, modifiers=Qt.NoModifier):
    SelectTool().on_click(ToolContext(
        viewport=viewport, world=V(0, 0), screen=QPointF(10.0, 10.0),
        modifiers=modifiers, snap=None))


def test_alt_click_cycles_front_to_back_and_wraps():
    vp = _StackedViewport()
    _click(vp, Qt.AltModifier)
    assert vp.scene.selection == {vp.front}
    _click(vp, Qt.AltModifier)
    assert vp.scene.selection == {vp.back}
    _click(vp, Qt.AltModifier)
    assert vp.scene.selection == {vp.front}


def test_plain_click_keeps_the_existing_front_most_behavior():
    vp = _StackedViewport()
    vp.scene.select([vp.back])
    _click(vp)
    assert vp.scene.selection == {vp.front}


def test_candidate_list_keeps_primary_priority_and_removes_duplicates():
    vp = _StackedViewport()
    candidates = SelectTool()._pick_candidates(vp, 10.0, 10.0, vp.front)
    assert candidates == [vp.front, vp.back]


def test_viewport_candidates_follow_ray_depth_and_collapse_group_faces():
    """The production helper reuses all face depths and returns a group once."""
    import numpy as np
    from types import SimpleNamespace
    from core.group import Group
    from core.mesh import Mesh

    front = Face([V(0, 0, 2), V(1, 0, 2), V(1, 1, 2)])
    grouped_a = Face([V(0, 0, 1), V(1, 0, 1), V(1, 1, 1)])
    grouped_b = Face([V(0, 0, .5), V(1, 0, .5), V(1, 1, .5)])
    hidden = Face([V(0, 0, -1), V(1, 0, -1), V(1, 1, -1)])
    group = Group(Mesh(), name="Assembly")
    idx = SimpleNamespace(entities=[(hidden, None), (grouped_b, group),
                                    (front, None), (grouped_a, group)])

    class _RayViewport:
        def _pixel_to_ray(self, _x, _y):
            return V(0, 0, 3), V(0, 0, -1)

        def _pick_index(self, near=None):
            return idx

        def _hover_face_t(self, _idx, _origin, _direction):
            return np.array([np.inf, 2.5, 1.0, 2.0])

    candidates = Viewport.pick_selection_candidates(_RayViewport(), 10, 10)
    assert candidates == [front, group]
