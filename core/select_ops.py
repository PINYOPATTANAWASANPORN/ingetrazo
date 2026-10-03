# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Right-click ▸ Select: grow a selection by what it touches or
by what it shares (issue #106, @pacaeiro).

Every function answers from the CURRENT editing context — the loose mesh the
scene exposes (``scene.faces``/``scene.edges``, which inside a group are that
group's), plus the groups at that level — never from the model around it,
the same rule Select All follows.
"""
from __future__ import annotations

from core.layers import layer_of
from core.mesh import Edge, Face


def context_entities(scene) -> list:
    """Entities a selection command may take in the current edit context.

    This deliberately mirrors :meth:`Scene.invert_selection`: hidden and
    locked entities stay out, and opening a group limits the command to that
    group's geometry and immediate children.
    """
    groups = _context_groups(scene)
    show_hidden = bool(scene.show_hidden_geometry)
    out = [e for e in scene.edges
           if scene.entity_selectable(e)
           and (show_hidden or not getattr(e, "hidden", False))]
    out += [f for f in scene.faces if scene.entity_selectable(f)]
    out += [g for g in groups if scene.entity_selectable(g)]
    out += [d for d in getattr(scene, "dimensions", ())
            if scene.entity_selectable(d)]
    return out


def by_type(scene, kind: str) -> list:
    """Select one familiar entity kind from the current context."""
    from core.dimension import Dimension
    from core.group import Group
    tests = {
        "faces": lambda e: isinstance(e, Face),
        "edges": lambda e: isinstance(e, Edge),
        "groups": lambda e: isinstance(e, Group) and not e.is_component(),
        "components": lambda e: isinstance(e, Group) and e.is_component(),
        "dimensions": lambda e: isinstance(e, Dimension),
    }
    test = tests.get(kind)
    return [e for e in context_entities(scene) if test and test(e)]


def entity_material_key(entity):
    """Hashable paint identity for a face or group placement."""
    attrs = (entity.attrs if isinstance(entity, Face)
             else getattr(entity, "material", None)) or {}
    if attrs.get("mat"):
        return ("mat", attrs["mat"])
    color = attrs.get("color")
    tex = attrs.get("texture")
    path = tex.get("path") if isinstance(tex, dict) else None
    if color is None and path is None:
        return None
    col = tuple(round(float(c), 4) for c in color) if color else None
    return ("paint", col, path)


def by_material(scene, key) -> list:
    """Faces and group/component placements carrying *key*."""
    return [e for e in context_entities(scene)
            if (isinstance(e, Face) or _is_group(e))
            and entity_material_key(e) == key]


def by_layer(scene, name: str) -> list:
    """Every taggable, selectable entity on *name* in this context."""
    return [e for e in context_entities(scene)
            if (isinstance(e, (Face, Edge)) or _is_group(e)
                or hasattr(e, "layer"))
            and layer_of(e) == name]


def all_connected(entities) -> list:
    """Everything physically connected to *entities* — the whole solid —
    walked through shared vertices (the classic triple click)."""
    seeds = []
    for e in entities:
        if isinstance(e, Face):
            seeds.extend(e.loop)
            for hole in e.hole_loops:
                seeds.extend(hole)
        elif isinstance(e, Edge):
            seeds.extend((e.v0, e.v1))
    seen_v = set(seeds)
    edges: set = set()
    faces: set = set()
    stack = list(seen_v)
    while stack:
        v = stack.pop()
        for e in v.edges:
            if e in edges:
                continue
            edges.add(e)
            for f in e.faces:
                if f in faces:
                    continue
                faces.add(f)
                for lp in (f.loop, *f.hole_loops):
                    for w in lp:
                        if w not in seen_v:
                            seen_v.add(w)
                            stack.append(w)
            w = e.other(v)
            if w not in seen_v:
                seen_v.add(w)
                stack.append(w)
    return list(edges) + list(faces)


def bounding_edges(entities) -> list:
    """The edges that outline the selected faces: those with exactly ONE of
    the selected faces on them (Select ▸ Bounding Edges)."""
    faces = {e for e in entities if isinstance(e, Face)}
    out = []
    seen = set()
    for f in faces:
        for e in _face_edges(f):
            if e in seen:
                continue
            seen.add(e)
            if sum(1 for g in e.faces if g in faces) == 1:
                out.append(e)
    return out


def _face_edges(face):
    """The edges running round *face*'s outer and hole loops."""
    for lp in (face.loop, *face.hole_loops):
        n = len(lp)
        for i in range(n):
            a, b = lp[i], lp[(i + 1) % n]
            for e in a.edges:
                if e.other(a) is b and face in e.faces:
                    yield e
                    break


def material_key(face):
    """What «the same material» means for a face: its named material when
    it has one, otherwise its colour and texture image. ``None`` = unpainted
    (the default material, which is a material too — the usual convention
    selects all the unpainted faces from an unpainted one)."""
    return entity_material_key(face)


def same_material(scene, entities) -> list:
    """Every face in the current context painted like one of the selected
    faces. Groups are matched by their own material when they carry one."""
    keys = {material_key(e) for e in entities if isinstance(e, Face)}
    out = [f for f in scene.faces if material_key(f) in keys] if keys else []
    group_mats = [getattr(g, "material", None) for g in entities
                  if _is_group(g) and getattr(g, "material", None)]
    if group_mats:
        out += [g for g in _context_groups(scene)
                if getattr(g, "material", None) in group_mats]
    return out


def same_layer(scene, entities) -> list:
    """Every edge, face and group in the current context on one of the
    selected entities' layers (Select ▸ All on Same Tag)."""
    layers = {layer_of(e) for e in entities
              if isinstance(e, (Face, Edge)) or _is_group(e)}
    if not layers:
        return []
    pool = list(scene.edges) + list(scene.faces) + list(_context_groups(scene))
    return [e for e in pool if layer_of(e) in layers]


def _is_group(e) -> bool:
    from core.group import Group
    return isinstance(e, Group)


def _context_groups(scene):
    ctx = getattr(scene, "edit_group", None)
    return scene.groups if ctx is None else (getattr(ctx, "children", None)
                                             or [])
