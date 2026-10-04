# SPDX-License-Identifier: GPL-3.0-or-later
"""The bounded, read-only context contract used by AI clients."""
from __future__ import annotations

import json

from core.ai_context import (assistant_context, capabilities, document_context,
                             find_entities, get_entities)
from core.group import Group
from core.mesh import Mesh
from core.scene import Scene


def _scene_with_tree() -> tuple[Scene, Group, Group, Group]:
    scene = Scene()
    wall = Group(Mesh(), name="North wall")
    window = Group(Mesh(), name="Kitchen window")
    chair = Group(Mesh(), name="Dining chair")
    wall.layer = "Architecture"
    wall.hidden = True
    wall.adopt([window])
    scene.groups.extend([wall, chair])
    scene.selection.add(chair)
    return scene, wall, window, chair


def test_document_context_is_bounded_tree_data_with_revision_cursor():
    scene, wall, window, chair = _scene_with_tree()

    first = document_context(scene, limit=2)
    assert first["schema_version"] == "1.0"
    assert first["content_revision"] == scene.content_version
    assert first["view_revision"] == scene.view_version
    assert first["selection"] == [{"type": "group", "id": chair.uid,
                                    "name": "Dining chair"}]
    assert [g["id"] for g in first["groups"]] == [wall.uid, window.uid]
    assert first["groups"][1]["parent_id"] == wall.uid
    assert first["groups"][0]["hidden"] is True
    assert first["next_cursor"]

    second = document_context(scene, limit=2, cursor=first["next_cursor"])
    assert [g["id"] for g in second["groups"]] == [chair.uid]
    assert second["next_cursor"] is None

    # Context includes selection, therefore a view change invalidates its
    # cursor even though a later content proposal need not become stale.
    scene.bump_view()
    stale = document_context(scene, cursor=first["next_cursor"])
    assert stale["stale"] is True
    assert stale["content_revision"] == scene.content_version


def test_find_entities_uses_content_cursor_and_detail_never_invents_ids():
    scene, wall, window, chair = _scene_with_tree()
    found = find_entities(scene, "window")
    assert [row["id"] for row in found["matches"]] == [window.uid]

    # A view-only change preserves a search cursor, while a model change does
    # not: entity lists are model data, not selection data.
    all_groups = find_entities(scene, limit=1)
    scene.bump_view()
    continued = find_entities(scene, limit=1, cursor=all_groups["next_cursor"])
    assert continued["stale"] is False
    assert find_entities(scene, "chair", cursor=all_groups["next_cursor"])["stale"]
    scene.version += 1
    assert find_entities(scene, cursor=all_groups["next_cursor"])["stale"]

    detail = get_entities(scene, [wall.uid, "does-not-exist", chair.uid])
    assert [row["id"] for row in detail["entities"]] == [wall.uid, chair.uid]
    # A container with children carries an identity placement to preserve the
    # group-tree invariant; detail exposes that transform faithfully.
    assert len(detail["entities"][0]["transform"]) == 16
    assert detail["missing"] == ["does-not-exist"]
    assert get_entities(scene, "not-an-array")["entities"] == []


def test_assistant_packet_is_small_json_and_capabilities_are_honest():
    scene, _wall, _window, _chair = _scene_with_tree()
    packet = json.loads(assistant_context(scene, limit=1))
    assert len(packet["groups"]) == 1
    assert packet["next_cursor"]
    assert "layers" not in packet                 # compact assistant packet

    caps = capabilities()
    assert caps["stable_entity_types"] == ["group", "component"]
    assert caps["topology_references"] == "revision_bound_only"
    assert caps["write_actions"] is True
    assert caps["preview_changes"] is True
    assert "rename_entities" in caps["write_action_types"]
