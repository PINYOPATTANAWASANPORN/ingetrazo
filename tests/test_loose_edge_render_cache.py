# SPDX-License-Identifier: GPL-3.0-or-later
"""Large loose-edge drawings stay cheap when only selection changes."""
from types import SimpleNamespace
from array import array

from PySide6.QtGui import QVector3D as V

from core.scene import Scene
from core.history import HideEdgesCommand, History
from core.layers import Layer, assign_layer
from views.viewport import Viewport


def _viewport_with_edges(count=200):
    scene = Scene()
    for i in range(count):
        scene.add_edge(V(float(i), 0, 0), V(float(i), 1, 0))
    return SimpleNamespace(scene=scene), scene


def test_selection_reuses_exact_loose_edge_block():
    viewport, scene = _viewport_with_edges()
    calls = 0
    visible = scene.entity_visible

    def counted(entity):
        nonlocal calls
        calls += 1
        return visible(entity)

    scene.entity_visible = counted
    first = Viewport._loose_hard_edge_block(viewport, False)
    assert calls == 200

    scene.select([scene.loose_mesh.edges[0]])
    second = Viewport._loose_hard_edge_block(viewport, False)
    assert second is first
    assert calls == 200


def test_content_edit_invalidates_loose_edge_block():
    viewport, scene = _viewport_with_edges(2)
    first = Viewport._loose_hard_edge_block(viewport, False)
    scene.add_edge(V(10, 0, 0), V(10, 1, 0))
    second = Viewport._loose_hard_edge_block(viewport, False)
    assert second is not first
    assert len(second) == len(first) + 24


def test_hidden_edit_context_has_an_empty_cached_block():
    viewport, scene = _viewport_with_edges(2)
    assert Viewport._loose_hard_edge_block(viewport, True) == b""
    assert Viewport._loose_hard_edge_block(viewport, False)


def test_loose_edge_block_tracks_tag_and_hide_undo():
    viewport, scene = _viewport_with_edges(3)
    history = History(scene)
    first, tagged, soft = scene.loose_mesh.edges
    scene.layers.append(Layer("Hidden tag", visible=False))
    assign_layer(tagged, "Hidden tag")
    soft.soft = True
    scene.version += 1

    def starts():
        coords = array("f")
        coords.frombytes(Viewport._loose_hard_edge_block(viewport, False))
        return [coords[i] for i in range(0, len(coords), 6)]

    assert starts() == [0.0]
    scene.layer("Hidden tag").visible = True
    scene.version += 1
    assert starts() == [0.0, 1.0]
    history.execute(HideEdgesCommand([first], hidden=True))
    assert starts() == [1.0]
    assert history.undo()
    assert starts() == [0.0, 1.0]
