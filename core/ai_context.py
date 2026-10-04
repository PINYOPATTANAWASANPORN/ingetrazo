# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Bounded, read-only model context for AI clients.

The AI assistant and MCP bridge must be able to name model objects without
asking a model to introspect the live Python API.  This module deliberately
exports only document data and stable ``Group.uid`` references.  Faces, edges
and vertices have no durable identity across topology rebuilds, so they are
reported as counts rather than as writable handles.

All list endpoints are cursor-paginated.  A cursor is tied to the revision it
was issued for; callers must restart a list after the document changes rather
than accidentally continuing through a different model.
"""
from __future__ import annotations

from collections.abc import Iterable
import hashlib
import json


SCHEMA_VERSION = "1.0"
DEFAULT_LIMIT = 50
MAX_LIMIT = 200


def _limit(value) -> int:
    try:
        value = int(value)
    except (TypeError, ValueError):
        return DEFAULT_LIMIT
    return max(1, min(value, MAX_LIMIT))


def _matrix(matrix) -> list[float] | None:
    """A JSON-safe 4×4 transform, or ``None`` for an untransformed group."""
    if matrix is None:
        return None
    return [float(v) for v in matrix.data()]


def _groups(scene) -> list[tuple[object, str | None, int]]:
    """Groups in deterministic tree order as ``(group, parent_uid, depth)``.

    A component prototype can be encountered more than once through nested
    placements.  It remains one addressable entity, which is why a UID is
    emitted only on its first visit.
    """
    out: list[tuple[object, str | None, int]] = []
    seen: set[int] = set()

    def walk(entries: Iterable, parent_uid: str | None, depth: int) -> None:
        for group in entries or ():
            marker = id(group)
            if marker in seen:
                continue
            seen.add(marker)
            out.append((group, parent_uid, depth))
            walk(getattr(group, "children", None) or (),
                 getattr(group, "uid", None), depth + 1)

    walk(getattr(scene, "groups", None) or (), None, 0)
    return out


def _group_entry(scene, group, parent_uid: str | None, depth: int,
                 detail: bool = False) -> dict:
    layer_name = getattr(group, "layer", None) or "Layer 0"
    layer = scene.layer(layer_name)
    mesh = getattr(group, "mesh", None)
    entry = {
        "id": group.uid,
        "type": "component" if group.is_component() else "group",
        "name": group.name,
        "parent_id": parent_uid,
        "depth": depth,
        "layer": layer_name,
        "hidden": bool(getattr(group, "hidden", False)),
        "locked": bool(getattr(group, "locked", False)),
        "visible": bool(scene.entity_visible(group)),
        "layer_visible": bool(layer.visible) if layer is not None else True,
        "layer_locked": bool(layer.locked) if layer is not None else False,
        "children": [child.uid for child in getattr(group, "children", ())],
        "face_count": len(getattr(mesh, "faces", ()) or ()),
        "edge_count": len(getattr(mesh, "edges", ()) or ()),
    }
    if detail:
        entry.update({
            "transform": _matrix(getattr(group, "xform", None)),
            "material": dict(getattr(group, "material", None) or {}),
            "ifc": dict(getattr(group, "ifc", None) or {}),
            "has_axes": getattr(group, "axes", None) is not None,
            "instance": getattr(group, "xform", None) is not None,
        })
    return entry


def _selection(scene) -> list[dict]:
    """Selection summary without inventing unstable face/edge identifiers."""
    groups = scene.groups_by_uid()
    ids = {id(g): uid for uid, g in groups.items()}
    selected: list[dict] = []
    for entity in scene.selection:
        uid = ids.get(id(entity))
        if uid is not None:
            selected.append({"type": "group", "id": uid,
                             "name": groups[uid].name})
        elif hasattr(entity, "loop"):
            selected.append({"type": "face", "stable": False})
        elif hasattr(entity, "v0"):
            selected.append({"type": "edge", "stable": False})
        else:
            selected.append({"type": type(entity).__name__.lower(),
                             "stable": False})
    return sorted(selected, key=lambda e: (e["type"], e.get("id", "")))


def _bounds(scene) -> dict | None:
    lo, hi = scene.bounds()
    if lo is None:
        return None
    return {"min": [lo.x(), lo.y(), lo.z()],
            "max": [hi.x(), hi.y(), hi.z()]}


def _cursor(prefix: str, content_revision: int, view_revision: int | None,
            offset: int) -> str:
    parts = [prefix, str(content_revision)]
    if view_revision is not None:
        parts.append(str(view_revision))
    parts.append(str(offset))
    return ":".join(parts)


def _offset(cursor, prefix: str, content_revision: int,
            view_revision: int | None) -> tuple[int, bool]:
    """Return ``(offset, stale)`` for a context cursor."""
    if cursor in (None, ""):
        return 0, False
    parts = str(cursor).split(":")
    expected = [prefix, str(content_revision)]
    if view_revision is not None:
        expected.append(str(view_revision))
    if len(parts) != len(expected) + 1 or parts[:-1] != expected:
        return 0, True
    try:
        offset = int(parts[-1])
    except ValueError:
        return 0, True
    return max(0, offset), False


def document_context(scene, limit=DEFAULT_LIMIT, cursor=None) -> dict:
    """A paginated document outline and the context that changes its meaning."""
    content = scene.content_version
    view = scene.view_version
    offset, stale = _offset(cursor, "context", content, view)
    if stale:
        return {"schema_version": SCHEMA_VERSION, "stale": True,
                "content_revision": content, "view_revision": view}
    groups = _groups(scene)
    limit = _limit(limit)
    page = groups[offset:offset + limit]
    end = offset + len(page)
    loose = scene.loose_mesh
    return {
        "schema_version": SCHEMA_VERSION,
        "stale": False,
        "content_revision": content,
        "view_revision": view,
        "units": dict(scene.units),
        "active_tag": scene.active_layer,
        "edit_context": (getattr(scene.edit_group, "uid", None)
                         if scene.edit_group is not None else None),
        "selection": _selection(scene),
        "bounds": _bounds(scene),
        "counts": {
            "loose_faces": len(loose.faces),
            "loose_edges": len(loose.edges),
            "groups": len(groups),
            "materials": len(scene.materials),
            "layers": len(scene.layers),
            "dimensions": len(scene.dimensions),
            "section_planes": len(scene.section_planes),
        },
        "layers": [{"name": layer.name, "visible": bool(layer.visible),
                    "locked": bool(layer.locked)} for layer in scene.layers],
        "groups": [_group_entry(scene, group, parent, depth)
                   for group, parent, depth in page],
        "next_cursor": (_cursor("context", content, view, end)
                        if end < len(groups) else None),
    }


def find_entities(scene, query="", limit=DEFAULT_LIMIT, cursor=None) -> dict:
    """Find groups/components by name, UID, or tag without Python discovery."""
    content = scene.content_version
    query_text = str(query or "")
    # A cursor is valid only for the same search.  Keep the query itself out
    # of the opaque cursor so unusual punctuation cannot alter its grammar.
    query_key = hashlib.sha256(query_text.encode()).hexdigest()[:16]
    offset, stale = _offset(cursor, "find-" + query_key, content, None)
    if stale:
        return {"schema_version": SCHEMA_VERSION, "stale": True,
                "content_revision": content}
    needle = query_text.casefold().strip()
    matches = [(g, parent, depth) for g, parent, depth in _groups(scene)
               if (not needle or needle in g.name.casefold()
                   or needle in g.uid.casefold()
                   or needle == (getattr(g, "layer", None) or "Layer 0").casefold())]
    limit = _limit(limit)
    page = matches[offset:offset + limit]
    end = offset + len(page)
    return {
        "schema_version": SCHEMA_VERSION,
        "stale": False,
        "content_revision": content,
        "query": query_text,
        "matches": [_group_entry(scene, group, parent, depth)
                    for group, parent, depth in page],
        "next_cursor": (_cursor("find-" + query_key, content, None, end)
                        if end < len(matches) else None),
    }


def get_entities(scene, entity_ids) -> dict:
    """Detailed records for stable group/component UIDs in ``entity_ids``."""
    raw_ids = entity_ids if isinstance(entity_ids, (list, tuple)) else ()
    requested = [str(item) for item in raw_ids[:MAX_LIMIT]]
    groups = _groups(scene)
    details = {group.uid: _group_entry(scene, group, parent, depth, True)
               for group, parent, depth in groups}
    return {
        "schema_version": SCHEMA_VERSION,
        "content_revision": scene.content_version,
        "entities": [details[uid] for uid in requested if uid in details],
        "missing": [uid for uid in requested if uid not in details],
        "truncated": len(raw_ids) > MAX_LIMIT,
    }


def capabilities() -> dict:
    """Stable feature declaration for clients that adapt to host versions."""
    return {
        "schema_version": SCHEMA_VERSION,
        "read_tools": ["get_document_context", "find_entities",
                       "get_entities", "get_capabilities"],
        "write_tools": ["propose_actions", "preview_changes",
                        "validate_changes", "commit_changes",
                        "discard_changes"],
        "write_action_types": ["rename_entities", "set_visibility",
                               "set_lock", "assign_tag", "assign_material",
                               "transform_entities"],
        "stable_entity_types": ["group", "component"],
        "topology_references": "revision_bound_only",
        "write_actions": True,
        "preview_changes": True,
        "multi_agent": False,
    }


def assistant_context(scene, limit: int = 20) -> str:
    """Small current-model packet safe to append to an assistant prompt.

    The assistant gets enough grounding for an ordinary request without
    receiving an unbounded Outliner.  External agents that need more use the
    paginated MCP tools instead.
    """
    context = document_context(scene, limit=limit)
    packet = {key: context[key] for key in (
        "schema_version", "content_revision", "view_revision", "units",
        "active_tag", "edit_context", "selection", "bounds", "counts",
        "groups", "next_cursor")}
    return json.dumps(packet, ensure_ascii=False, separators=(",", ":"))
