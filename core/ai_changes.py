# SPDX-License-Identifier: GPL-3.0-or-later
"""Validated, preview-first AI changes for stable model containers.

A proposal is pure data until the user approves it in an IngeTrazo AI panel.
Commit rechecks the content revision and records property, transform, and
primitive-creation changes as one history command.
"""
from __future__ import annotations

import hashlib
import copy
import json
import math
from dataclasses import dataclass

from PySide6.QtGui import QMatrix4x4, QVector3D

from core.history import (Command, MoveGroupCommand, RotateGroupCommand,
                          ScaleGroupCommand, rotation_matrix, scale_matrix)
from core.group import Group
from core.layers import DEFAULT_LAYER
from core.mesh import Mesh

MAX_ACTIONS = 100
MAX_ENTITIES = 200
MAX_NAME = 200

ACTION_FIELDS = {
    "rename_entities": "name",
    "set_visibility": "hidden",
    "set_lock": "locked",
    "assign_tag": "layer",
    "assign_material": "material",
}

TRANSFORM_ACTION = "transform_entities"
CREATE_ACTIONS = {"create_box", "create_cylinder", "create_wall",
                  "create_slab", "create_component_instance"}


def _error(code: str, message: str, **extra) -> dict:
    return {"ok": False, "code": code, "message": message, **extra}


def _public_change(change: dict) -> dict:
    return {key: change[key] for key in (
        "entity_id", "entity_type", "entity_name", "field", "before",
        "after")}


class AIPropertyChangeCommand(Command):
    """Apply one validated property change set as one undo item."""

    def __init__(self, changes: list[dict], task_id: str) -> None:
        self.changes = list(changes)
        self.task_id = task_id
        self.description = f"AI task: {task_id}"

    @staticmethod
    def _set(change: dict, value) -> None:
        command = change.get("_command")
        if command is not None:
            return
        group = change["_entity"]
        field = change["field"]
        if field == "layer":
            group.layer = None if value == DEFAULT_LAYER else value
        else:
            setattr(group, field, value)

    def _apply(self, scene, side: str) -> None:
        ordered = self.changes if side == "after" else reversed(self.changes)
        for change in ordered:
            command = change.get("_command")
            if command is not None:
                (command.do(scene) if side == "after" else command.undo(scene))
                continue
            self._set(change, change[side])
            if side == "after" and change["field"] in ("hidden", "locked") \
                    and change[side]:
                scene.selection.discard(change["_entity"])
        # Visibility and tags affect cached group render chunks.  Naming and
        # locking do not, but invalidating once keeps this compound command
        # deterministic and is cheap compared with a model edit.
        from core.history import _dirty_group_chunks
        _dirty_group_chunks(scene)
        scene.version += 1

    def do(self, scene) -> None:
        self._apply(scene, "after")

    def undo(self, scene) -> None:
        self._apply(scene, "before")


class AICreateGroupCommand(Command):
    """Insert one prepared container without rebuilding geometry."""

    def __init__(self, group: Group, parent: Group | None = None) -> None:
        self.group = group
        self.parent = parent

    def do(self, scene) -> None:
        target = scene.groups if self.parent is None else self.parent.children
        if self.group not in target:
            target.append(self.group)
        scene.selection.clear()
        scene.selection.add(self.group)
        scene.version += 1

    def undo(self, scene) -> None:
        target = scene.groups if self.parent is None else self.parent.children
        if self.group in target:
            target.remove(self.group)
        scene.selection.discard(self.group)
        scene.version += 1


@dataclass
class _Proposal:
    task_id: str
    intent: str
    base_revision: int
    idempotency_key: str
    fingerprint: str
    actions: list[dict]
    changes: list[dict]
    status: str = "preview_ready"

    def public(self) -> dict:
        return {
            "ok": True,
            "task_id": self.task_id,
            "intent": self.intent,
            "status": self.status,
            "base_revision": self.base_revision,
            "affected_entities": sorted({
                change["entity_id"] for change in self.changes}),
            "changes": [_public_change(change) for change in self.changes],
            "validation": {"valid": True, "errors": [], "warnings": []},
            "requires_user_approval": True,
        }


class AIChangeService:
    """One-document proposal, approval, idempotency and write-lease service."""

    def __init__(self, scene, history, tasks=None) -> None:
        self.scene = scene
        self.history = history
        self.tasks = tasks
        self._active: _Proposal | None = None
        self._by_task: dict[str, dict] = {}
        self._by_key: dict[str, tuple[str, str, dict]] = {}

    def summary(self) -> dict | None:
        proposal = self._active
        if proposal is None:
            return None
        return {"task_id": proposal.task_id, "status": proposal.status,
                "change_count": len(proposal.changes),
                "affected_count": len({c["entity_id"]
                                       for c in proposal.changes}),
                "changes": [_public_change(c) for c in proposal.changes]}

    @staticmethod
    def _fingerprint(intent, base_revision, actions) -> str:
        raw = json.dumps({"intent": intent, "base_revision": base_revision,
                          "actions": actions}, sort_keys=True,
                         separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    def _vector(value, label: str, allow_zero: bool = True):
        if not isinstance(value, (list, tuple)) or len(value) != 3:
            return _error("invalid_transform", f"{label} must contain 3 numbers")
        try:
            raw = [float(item) for item in value]
        except (TypeError, ValueError):
            return _error("invalid_transform", f"{label} must contain 3 numbers")
        if not all(math.isfinite(item) for item in raw):
            return _error("invalid_transform", f"{label} must contain finite numbers")
        vector = QVector3D(*raw)
        if not all(math.isfinite(value) for value in
                   (vector.x(), vector.y(), vector.z())):
            return _error("invalid_transform", f"{label} exceeds coordinate precision")
        if not allow_zero and vector.lengthSquared() <= 1e-18:
            return _error("invalid_transform", f"{label} must not be zero")
        return raw, vector

    @staticmethod
    def _bounds(group, matrix=None) -> dict | None:
        from core.group import world_mesh
        points = [vertex.position for vertex in world_mesh(group).vertices]
        if matrix is not None:
            points = [matrix.map(point) for point in points]
        if not points:
            return None
        lo = [min(getattr(point, axis)() for point in points)
              for axis in ("x", "y", "z")]
        hi = [max(getattr(point, axis)() for point in points)
              for axis in ("x", "y", "z")]
        return {"min": lo, "max": hi,
                "size": [hi[index] - lo[index] for index in range(3)]}

    def _creation_style(self, raw: dict):
        name = str(raw.get("name") or "").strip()
        if not name or len(name) > MAX_NAME:
            return _error("invalid_name",
                          f"name must contain 1-{MAX_NAME} characters")
        if not isinstance(raw.get("component", False), bool):
            return _error("invalid_component", "component must be boolean")
        tag = str(raw.get("tag") or getattr(
            self.scene, "active_layer", None) or DEFAULT_LAYER).strip()
        layer = self.scene.layer(tag)
        if layer is None:
            return _error("unknown_tag", f"tag {tag!r} does not exist")
        if not layer.visible or layer.locked:
            return _error("unavailable_tag",
                          f"tag {tag!r} is hidden or locked")
        material_name = raw.get("material")
        material = None
        if material_name not in (None, ""):
            material_name = str(material_name).strip()
            material = self.scene.materials.get(material_name)
            if material is None:
                return _error("unknown_material",
                              f"material {material_name!r} does not exist")
        return name, bool(raw.get("component", False)), tag, material_name, material

    @staticmethod
    def _box_mesh(origin: QVector3D, size: list[float]) -> Mesh:
        x, y, z = origin.x(), origin.y(), origin.z()
        dx, dy, dz = size
        points = [
            QVector3D(x, y, z), QVector3D(x + dx, y, z),
            QVector3D(x + dx, y + dy, z), QVector3D(x, y + dy, z),
            QVector3D(x, y, z + dz), QVector3D(x + dx, y, z + dz),
            QVector3D(x + dx, y + dy, z + dz),
            QVector3D(x, y + dy, z + dz),
        ]
        mesh = Mesh()
        for indices in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
                        (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
            mesh.add_face([points[index] for index in indices])
        return mesh

    @staticmethod
    def _cylinder_mesh(origin: QVector3D, radius: float, height: float,
                       segments: int) -> Mesh:
        bottom = []
        top = []
        for index in range(segments):
            angle = 2.0 * math.pi * index / segments
            x = origin.x() + radius * math.cos(angle)
            y = origin.y() + radius * math.sin(angle)
            bottom.append(QVector3D(x, y, origin.z()))
            top.append(QVector3D(x, y, origin.z() + height))
        mesh = Mesh()
        mesh.add_face(list(reversed(bottom)))
        mesh.add_face(top)
        for index in range(segments):
            nxt = (index + 1) % segments
            mesh.add_face([bottom[index], bottom[nxt], top[nxt], top[index]])
        # Hide the facet seams while keeping both circular rims crisp.
        for index in range(segments):
            a = mesh.vertex_at(bottom[index])
            b = mesh.vertex_at(top[index])
            edge = mesh.find_edge(a, b) if a is not None and b is not None else None
            if edge is not None:
                edge.soft = True
        return mesh

    @staticmethod
    def _positive(raw, key: str) -> float | dict:
        try:
            value = float(raw.get(key))
        except (TypeError, ValueError):
            value = math.nan
        if not math.isfinite(value) or value <= 0 or value > 1e6:
            return _error("invalid_dimension",
                          f"{key} must be finite, positive, and at most 1000000")
        return value

    def _creation_vector(self, value, label):
        result = self._vector(value, label)
        if isinstance(result, dict):
            return result
        if any(abs(number) > 1e6 for number in result[0]):
            return _error("invalid_coordinate", f"{label} values must be within +/-1000000")
        return result

    @staticmethod
    def _wall_mesh(start: QVector3D, end: QVector3D, height: float,
                   thickness: float, openings: list[dict]) -> Mesh:
        delta = end - start
        length = math.hypot(delta.x(), delta.y())
        along = QVector3D(delta.x() / length, delta.y() / length, 0)
        normal = QVector3D(-along.y() * thickness,
                           along.x() * thickness, 0)

        def point(offset, z):
            return start + along * offset + QVector3D(0, 0, z)

        doors = [item for item in openings if item["sill"] == 0]
        windows = [item for item in openings if item["sill"] > 0]
        outline = [point(0, 0)]
        for item in doors:
            x, w, h = item["offset"], item["width"], item["height"]
            outline.extend((point(x, 0), point(x, h),
                            point(x + w, h), point(x + w, 0)))
        outline.extend((point(length, 0), point(length, height),
                        point(0, height)))
        outline = [p for i, p in enumerate(outline)
                   if i == 0 or (p - outline[i - 1]).length() > 1e-9]
        holes = [[point(item["offset"], item["sill"]),
                  point(item["offset"], item["sill"] + item["height"]),
                  point(item["offset"] + item["width"],
                        item["sill"] + item["height"]),
                  point(item["offset"] + item["width"], item["sill"])]
                 for item in windows]
        mesh = Mesh()
        mesh.add_face(outline, holes or None)
        mesh.add_face([p + normal for p in reversed(outline)],
                      [[p + normal for p in reversed(h)] for h in holes] or None)
        for ring in (outline, *holes):
            for index, a in enumerate(ring):
                b = ring[(index + 1) % len(ring)]
                mesh.add_face([a, a + normal, b + normal, b])
        return mesh

    def _creation_parent(self, raw: dict):
        space = raw.get("coordinate_space", "model")
        parent_id = raw.get("parent_id")
        if space not in ("model", "parent") or \
                (space == "model") != (parent_id is None):
            return _error("invalid_coordinate_space",
                          "model coordinates need no parent_id; parent coordinates need parent_id")
        if parent_id is None:
            return None, None
        parent = self.scene.groups_by_uid().get(str(parent_id))
        if parent is None:
            return _error("unknown_entity", "parent_id does not exist")
        if not parent.is_instance() or parent.is_component():
            return _error("invalid_parent", "parent must be a non-component instance container")
        if parent.locked or not self.scene.entity_visible(parent):
            return _error("unavailable_parent", "parent is hidden or locked")
        # A component ancestor owns shared definition content. Inserting into
        # only one copy would silently diverge the other instances.
        def find(group, ancestors):
            if group is parent:
                return ancestors + [group]
            for child in group.children:
                found = find(child, ancestors + [group])
                if found:
                    return found
            return None
        path = next((found for root in self.scene.groups
                     if (found := find(root, []))), None)
        if path is None or any(g.is_component() for g in path[:-1]):
            return _error("invalid_parent", "parent belongs to a shared component definition")
        if any(not self.scene.entity_selectable(g) or
               not self.scene.entity_visible(g) for g in path):
            return _error("unavailable_parent", "parent or ancestor is hidden or locked")
        frame = QMatrix4x4()
        for group in path:
            if group.xform is not None:
                frame = frame * group.xform
        return parent, frame

    @staticmethod
    def _copy_component(source):
        # copy_group may promote classic children on the live source. A preview
        # instead prepares fresh placements and shares only immutable meshes.
        group = Group(source.mesh, source.name)
        for field in Group.__slots__:
            if field not in {"mesh", "uid", "children", "xform", "axes",
                             "owner", "context"}:
                setattr(group, field, copy.deepcopy(getattr(source, field)))
        group.xform = QMatrix4x4(source.xform) if source.xform is not None else QMatrix4x4()
        group.component = source.is_component()
        group.axes = QMatrix4x4(source.axes) if source.axes is not None else None
        group.children = [AIChangeService._copy_component(child)
                          for child in source.children]
        return group

    def _create(self, raw: dict, kind: str):
        if self.scene.edit_group is not None:
            return _error(
                "nested_creation_unsupported",
                "close the group edit context before proposing typed creation")
        placement = self._creation_parent(raw)
        if isinstance(placement, dict):
            return placement
        parent, parent_frame = placement
        space = "parent" if parent is not None else "model"
        if kind == "create_component_instance":
            if parent is not None:
                return _error("invalid_parent", "component copies currently require model coordinates")
            source_id = str(raw.get("source_id") or "")
            source = self.scene.groups_by_uid().get(source_id)
            if source is None or source not in self.scene.groups:
                return _error("unknown_entity", "source_id must name a top-level component")
            if (not source.is_component() or not self.scene.entity_selectable(source) or
                    not self.scene.entity_visible(source)):
                return _error("unavailable_source", "source must be a visible, unlocked component")
            from core.group import iter_placements
            if any(g.xform is None for g, _ in iter_placements(source)):
                return _error("unsupported_source",
                              "component contains classic children; convert their placements before copying")
            parsed = self._creation_vector(raw.get("offset"), "offset")
            if isinstance(parsed, dict):
                return parsed
            offset, delta = parsed
            name = str(raw.get("name") or source.name).strip()
            if not name or len(name) > MAX_NAME:
                return _error("invalid_name", f"name must contain 1-{MAX_NAME} characters")
            group = self._copy_component(source)
            translation = QMatrix4x4()
            translation.translate(delta)
            group.xform = translation * group.xform
            group.name = name
            after = {"shape": "component_instance", "source_id": source_id,
                     "coordinate_space": space, "offset": offset,
                     "bounds": self._bounds(group), "component": True}
            normalised = {"action": kind, "source_id": source_id,
                          "name": name, "coordinate_space": space,
                          "offset": offset}
            change = {"_entity": group, "_command": AICreateGroupCommand(group),
                      "entity_id": group.uid, "entity_type": "component",
                      "entity_name": name, "field": "created",
                      "before": None, "after": after}
            return normalised, change
        style = self._creation_style(raw)
        if isinstance(style, dict):
            return style
        name, component, tag, material_name, material = style
        parsed = self._creation_vector(raw.get("origin", [0, 0, 0]), "origin")
        if isinstance(parsed, dict):
            return parsed
        origin_values, origin = parsed
        local_origin = QVector3D(0, 0, 0) if component else origin
        placement_origin = origin

        if kind == "create_box":
            size_result = self._vector(raw.get("size"), "size")
            if isinstance(size_result, dict):
                return size_result
            size, _vector = size_result
            if any(value <= 0 or value > 1e6 for value in size):
                return _error("invalid_size",
                              "box size values must be greater than 0 and at most 1000000")
            mesh = self._box_mesh(local_origin, size)
            parameters = {"origin": origin_values, "size": size}
        elif kind == "create_cylinder":
            try:
                radius = float(raw.get("radius"))
                height = float(raw.get("height"))
                segments = int(raw.get("segments", 24))
            except (TypeError, ValueError):
                return _error("invalid_cylinder",
                              "radius, height and segments must be numbers")
            if (not math.isfinite(radius) or not math.isfinite(height)
                    or radius <= 0 or height <= 0
                    or radius > 1e6 or height > 1e6):
                return _error("invalid_cylinder",
                              "radius and height must be finite, positive, and at most 1000000")
            if segments < 3 or segments > 128:
                return _error("invalid_segments",
                              "segments must be an integer between 3 and 128")
            mesh = self._cylinder_mesh(local_origin, radius, height, segments)
            parameters = {"origin": origin_values, "radius": radius,
                          "height": height, "segments": segments}
        elif kind == "create_slab":
            size_result = self._vector(raw.get("size"), "size")
            if isinstance(size_result, dict):
                return size_result
            size, _vector = size_result
            if any(value <= 0 or value > 1e6 for value in size):
                return _error("invalid_size", "slab size values must be positive and at most 1000000")
            mesh = self._box_mesh(local_origin, size)
            parameters = {"origin": origin_values, "size": size}
        else:  # create_wall, with optional door/window openings
            start_result = self._creation_vector(raw.get("start"), "start")
            end_result = self._creation_vector(raw.get("end"), "end")
            if isinstance(start_result, dict):
                return start_result
            if isinstance(end_result, dict):
                return end_result
            start_values, start = start_result
            end_values, end = end_result
            height = self._positive(raw, "height")
            thickness = self._positive(raw, "thickness")
            if isinstance(height, dict):
                return height
            if isinstance(thickness, dict):
                return thickness
            length = math.hypot(end.x() - start.x(), end.y() - start.y())
            if length <= 1e-6 or abs(end.z() - start.z()) > 1e-6:
                return _error("invalid_wall", "start and end need distinct XY positions at the same height")
            openings = raw.get("openings", [])
            if not isinstance(openings, list) or len(openings) > 32:
                return _error("invalid_openings", "openings must be an array of at most 32 items")
            parsed_openings = []
            for item in openings:
                if not isinstance(item, dict):
                    return _error("invalid_openings", "each opening needs offset, sill, width and height")
                try:
                    opening = {key: float(item[key]) for key in
                               ("offset", "sill", "width", "height")}
                except (KeyError, TypeError, ValueError):
                    return _error("invalid_openings", "each opening needs offset, sill, width and height")
                x, sill, width, opening_height = (opening[key] for key in
                                                  ("offset", "sill", "width", "height"))
                if (not all(math.isfinite(v) for v in opening.values()) or
                        x <= 1e-6 or sill < 0 or width <= 1e-6 or
                        opening_height <= 1e-6 or x + width >= length - 1e-6 or
                        sill + opening_height >= height - 1e-6):
                    return _error("invalid_openings", "opening must fit strictly inside the wall except at the base")
                parsed_openings.append(opening)
            parsed_openings.sort(key=lambda item: item["offset"])
            if any(a["offset"] + a["width"] >= b["offset"] - 1e-6
                   for a, b in zip(parsed_openings, parsed_openings[1:])):
                return _error("invalid_openings", "openings must not overlap or touch")
            placement_origin = start
            local_start = QVector3D(0, 0, 0) if component else start
            local_end = local_start + (end - start)
            mesh = self._wall_mesh(local_start, local_end, height,
                                   thickness, parsed_openings)
            parameters = {"start": start_values, "end": end_values,
                          "height": height, "thickness": thickness,
                          "openings": parsed_openings}

        group = Group(mesh, name)
        if (len(mesh.faces) < 4 or any(len(edge.faces) != 2 for edge in mesh.edges)
                or any(not math.isfinite(value) for vertex in mesh.vertices
                       for value in (vertex.position.x(), vertex.position.y(),
                                     vertex.position.z()))):
            return _error("invalid_geometry",
                          "dimensions do not produce a closed solid at model precision")
        if component:
            group.xform = QMatrix4x4()
            group.xform.translate(placement_origin)
        elif parent is not None:
            group.xform = QMatrix4x4()
            group.component = False
        group.layer = None if tag == DEFAULT_LAYER else tag
        group.material = material.face_attrs() if material is not None else None
        after = {"shape": kind.removeprefix("create_"),
                 "bounds": self._bounds(group, parent_frame), "tag": tag,
                 "material": material_name or None,
                 "component": component, "coordinate_space": space,
                 "parent_id": parent.uid if parent is not None else None,
                 **parameters}
        normalised = {"action": kind, "name": name,
                      "component": component, "tag": tag,
                      "material": material_name or None,
                      "coordinate_space": space,
                      "parent_id": parent.uid if parent is not None else None,
                      **parameters}
        change = {"_entity": group,
                  "_command": AICreateGroupCommand(group, parent),
                  "entity_id": group.uid,
                  "entity_type": "component" if component else "group",
                  "entity_name": name, "field": "created",
                  "before": None, "after": after}
        return normalised, change

    def _transform(self, raw: dict, group, index: int):
        operation = str(raw.get("operation") or "").strip().lower()
        before = self._bounds(group)
        if operation == "translate":
            parsed = self._vector(raw.get("delta"), "delta")
            if isinstance(parsed, dict):
                return parsed
            values, delta = parsed
            matrix = QMatrix4x4()
            matrix.translate(delta)
            command = MoveGroupCommand(group, delta)
            normalised = {"action": TRANSFORM_ACTION,
                          "entity_ids": [group.uid],
                          "operation": operation, "delta": values}
            parameters = {"delta": values}
            no_change = all(abs(value) <= 1e-12 for value in values)
        elif operation == "rotate":
            center_result = self._vector(raw.get("center"), "center")
            axis_result = self._vector(raw.get("axis"), "axis", False)
            if isinstance(center_result, dict):
                return center_result
            if isinstance(axis_result, dict):
                return axis_result
            try:
                degrees = float(raw.get("degrees"))
            except (TypeError, ValueError):
                degrees = math.nan
            if not math.isfinite(degrees) or abs(degrees) > 3600:
                return _error("invalid_transform",
                              "degrees must be finite and between -3600 and 3600")
            center_values, center = center_result
            axis_values, axis = axis_result
            matrix = rotation_matrix(center, axis, degrees)
            command = RotateGroupCommand(group, center, axis, degrees)
            normalised = {"action": TRANSFORM_ACTION,
                          "entity_ids": [group.uid],
                          "operation": operation, "center": center_values,
                          "axis": axis_values, "degrees": degrees}
            parameters = {"center": center_values, "axis": axis_values,
                          "degrees": degrees}
            no_change = abs(degrees) % 360.0 <= 1e-12
        elif operation == "scale":
            center_result = self._vector(raw.get("center"), "center")
            if isinstance(center_result, dict):
                return center_result
            factor_raw = raw.get("factor")
            if isinstance(factor_raw, (list, tuple)):
                factor_result = self._vector(factor_raw, "factor")
                if isinstance(factor_result, dict):
                    return factor_result
                factor = factor_result[0]
            else:
                try:
                    factor = float(factor_raw)
                except (TypeError, ValueError):
                    factor = math.nan
            factors = factor if isinstance(factor, list) else [factor] * 3
            if (not all(math.isfinite(value) for value in factors)
                    or any(abs(value) <= 1e-9 or abs(value) > 1000
                           for value in factors)):
                return _error("invalid_transform",
                              "scale factors must be finite, non-zero, and at most 1000")
            center_values, center = center_result
            stored_factor = factor if isinstance(factor, list) else float(factor)
            matrix = scale_matrix(center, stored_factor)
            command = ScaleGroupCommand(group, center, stored_factor)
            normalised = {"action": TRANSFORM_ACTION,
                          "entity_ids": [group.uid],
                          "operation": operation, "center": center_values,
                          "factor": stored_factor}
            parameters = {"center": center_values, "factor": stored_factor}
            no_change = all(abs(value - 1.0) <= 1e-12 for value in factors)
        else:
            return _error("invalid_transform",
                          f"action {index} operation must be translate, rotate, or scale")
        if no_change:
            return normalised, None
        return normalised, {
            "_entity": group, "_command": command,
            "entity_id": group.uid,
            "entity_type": "component" if group.is_component() else "group",
            "entity_name": group.name,
            "field": operation,
            "before": {"bounds": before},
            "after": {"bounds": self._bounds(group, matrix), **parameters},
        }

    def _stale(self, proposal: _Proposal) -> dict | None:
        current = self.scene.content_version
        if current == proposal.base_revision:
            return None
        result = _error(
            "stale_revision",
            "The document changed after this preview; propose it again.",
            task_id=proposal.task_id, base_revision=proposal.base_revision,
            content_revision=current, status="stale")
        self._by_task[proposal.task_id] = result
        self._by_key[proposal.idempotency_key] = (
            proposal.task_id, proposal.fingerprint, result)
        if self._active is proposal:
            self._active = None
        if self.tasks is not None:
            self.tasks.transition(proposal.task_id, "stale", result)
        return result

    def _normalise(self, actions) -> tuple[list[dict], list[dict]] | dict:
        if not isinstance(actions, list) or not actions:
            return _error("invalid_actions", "actions must be a non-empty array")
        if len(actions) > MAX_ACTIONS:
            return _error("too_many_actions",
                          f"at most {MAX_ACTIONS} actions are allowed")
        groups = self.scene.groups_by_uid()
        transform_ids = {str(uid) for action in actions if isinstance(action, dict)
                         and action.get("action") == TRANSFORM_ACTION
                         for uid in (action.get("entity_ids") or [])}
        normalised: list[dict] = []
        changes: dict[tuple[str, str], dict] = {}
        transformed: set[str] = set()
        total_entities = 0
        for index, raw in enumerate(actions):
            if not isinstance(raw, dict):
                return _error("invalid_action", f"action {index} must be an object")
            kind = str(raw.get("action") or "")
            field = ACTION_FIELDS.get(kind)
            if field is None and kind != TRANSFORM_ACTION and kind not in CREATE_ACTIONS:
                return _error("unsupported_action", f"unsupported action {kind!r}")
            if kind in CREATE_ACTIONS:
                from core.group import iter_placements
                reference_ids = {str(raw[key]) for key in ("parent_id", "source_id")
                                 if raw.get(key) is not None}
                if any(reference_ids.intersection(g.uid for g, _ in iter_placements(groups[uid]))
                       for uid in transform_ids if uid in groups):
                    return _error("conflicting_creation_transform",
                                  "transform the creation parent/source in a separate proposal")
                total_entities += 1
                if total_entities > MAX_ENTITIES:
                    return _error("too_many_entities",
                                  f"at most {MAX_ENTITIES} entity references are allowed")
                built = self._create(raw, kind)
                if isinstance(built, dict):
                    return built
                entry, change = built
                normalised.append(entry)
                changes[(change["entity_id"], "created")] = change
                continue
            ids = raw.get("entity_ids")
            if not isinstance(ids, list) or not ids:
                return _error("invalid_entities",
                              f"action {index} needs entity_ids")
            ids = list(dict.fromkeys(str(uid) for uid in ids))
            total_entities += len(ids)
            if total_entities > MAX_ENTITIES:
                return _error("too_many_entities",
                              f"at most {MAX_ENTITIES} entity references are allowed")
            missing = [uid for uid in ids if uid not in groups]
            if missing:
                return _error("unknown_entity", "one or more entities do not exist",
                              entity_ids=missing)

            if kind == TRANSFORM_ACTION:
                if len(ids) != 1:
                    return _error("invalid_transform",
                                  "each transform action must target exactly one entity")
                group = groups[ids[0]]
                if group not in self.scene.groups:
                    return _error(
                        "nested_transform_unsupported",
                        "nested entities cannot be transformed safely in world coordinates yet",
                        entity_id=group.uid)
                if group.uid in transformed:
                    return _error(
                        "duplicate_transform",
                        "use one transform action per entity in a change set",
                        entity_id=group.uid)
                if group.locked:
                    return _error("entity_locked",
                                  f"entity {group.uid} is locked",
                                  entity_id=group.uid)
                built = self._transform(raw, group, index)
                if isinstance(built, dict):
                    return built
                entry, change = built
                normalised.append(entry)
                if change is not None:
                    changes[(group.uid, f"transform-{index}")] = change
                transformed.add(group.uid)
                continue

            if field == "name":
                value = str(raw.get("name") or "").strip()
                if not value or len(value) > MAX_NAME:
                    return _error("invalid_name",
                                  f"name must contain 1-{MAX_NAME} characters")
            elif field == "hidden":
                if not isinstance(raw.get("visible"), bool):
                    return _error("invalid_visibility", "visible must be boolean")
                value = not raw["visible"]
            elif field == "locked":
                if not isinstance(raw.get("locked"), bool):
                    return _error("invalid_lock", "locked must be boolean")
                value = raw["locked"]
            elif field == "layer":
                value = str(raw.get("tag") or "").strip()
                layer = self.scene.layer(value)
                if layer is None:
                    return _error("unknown_tag", f"tag {value!r} does not exist")
                if not layer.visible or layer.locked:
                    return _error("unavailable_tag",
                                  f"tag {value!r} is hidden or locked")
            else:
                material_name = raw.get("material")
                if material_name in (None, ""):
                    value = None
                else:
                    material_name = str(material_name).strip()
                    material = self.scene.materials.get(material_name)
                    if material is None:
                        return _error("unknown_material",
                                      f"material {material_name!r} does not exist")
                    value = material.face_attrs()

            entry = {"action": kind, "entity_ids": ids}
            entry[{"name": "name", "hidden": "visible",
                   "locked": "locked", "layer": "tag",
                   "material": "material"}[field]] = (
                       not value if field == "hidden" else value)
            if field == "material":
                entry["material"] = value.get("mat") if value else None
            normalised.append(entry)
            for uid in ids:
                group = groups[uid]
                if group.locked and field != "locked":
                    return _error("entity_locked",
                                  f"entity {uid} is locked", entity_id=uid)
                before = (getattr(group, field) if field != "layer" else
                          (getattr(group, "layer", None) or DEFAULT_LAYER))
                if field == "material":
                    before = dict(before) if before else None
                key = (uid, field)
                changes[key] = {
                    "_entity": group,
                    "entity_id": uid,
                    "entity_type": ("component" if group.is_component()
                                    else "group"),
                    "entity_name": group.name,
                    "field": field,
                    "before": before,
                    "after": value,
                }
        return normalised, [change for change in changes.values()
                            if change["before"] != change["after"]]

    def propose(self, task_id="", intent="", base_revision=None,
                idempotency_key="", actions=None) -> dict:
        task_id = str(task_id or "").strip()
        key = str(idempotency_key or "").strip()
        if not task_id or len(task_id) > 100:
            return _error("invalid_task_id", "task_id is required (max 100 characters)")
        if len(key) < 8 or len(key) > 200:
            return _error("invalid_idempotency_key",
                          "idempotency_key must contain 8-200 characters")
        try:
            base = int(base_revision)
        except (TypeError, ValueError):
            return _error("invalid_revision", "base_revision must be an integer")
        if self.tasks is not None:
            task = self.tasks.task(task_id)
            if task is not None and not str(intent or "").strip():
                intent = task.intent
        fingerprint = self._fingerprint(str(intent or ""), base, actions)
        prior = self._by_key.get(key)
        if prior is not None:
            prior_task, prior_fingerprint, result = prior
            if prior_task != task_id or prior_fingerprint != fingerprint:
                return _error("idempotency_conflict",
                              "idempotency_key was already used for different input")
            return dict(result)
        if self.tasks is not None:
            task_error = self.tasks.validate_proposal(task_id, base, actions or [])
            if task_error is not None:
                return task_error
        if self._active is not None and self._active.task_id != task_id:
            return _error("busy", "another AI change set holds the write lease",
                          task_id=self._active.task_id)
        if base != self.scene.content_version:
            result = _error("stale_revision", "base_revision is not current",
                            content_revision=self.scene.content_version)
            if self.tasks is not None:
                self.tasks.transition(task_id, "stale", result)
            return result
        built = self._normalise(actions)
        if isinstance(built, dict):
            return built
        normalised, changes = built
        proposal = _Proposal(task_id, str(intent or ""), base, key,
                             fingerprint, normalised, changes)
        result = proposal.public()
        self._active = proposal
        self._by_task[task_id] = result
        self._by_key[key] = (task_id, fingerprint, result)
        if self.tasks is not None:
            self.tasks.transition(task_id, "preview_ready", result)
        return dict(result)

    def preview(self, task_id="") -> dict:
        task_id = str(task_id or "")
        if self._active is not None and self._active.task_id == task_id:
            stale = self._stale(self._active)
            return stale or self._active.public()
        result = self._by_task.get(task_id)
        return dict(result) if result is not None else _error(
            "unknown_task", f"task {task_id!r} does not exist")

    def validate(self, task_id="") -> dict:
        result = self.preview(task_id)
        if not result.get("ok"):
            return result
        return {"ok": True, "task_id": result["task_id"],
                "status": result["status"],
                "base_revision": result["base_revision"],
                "content_revision": self.scene.content_version,
                "validation": result["validation"],
                "affected_entities": result["affected_entities"]}

    def request_commit(self, task_id="", base_revision=None,
                       idempotency_key="") -> dict:
        proposal = self._active
        if proposal is None or proposal.task_id != str(task_id or ""):
            return self.preview(task_id)
        stale = self._stale(proposal)
        if stale:
            return stale
        try:
            revision = int(base_revision)
        except (TypeError, ValueError):
            revision = None
        if revision != proposal.base_revision or str(
                idempotency_key or "") != proposal.idempotency_key:
            return _error("proposal_mismatch",
                          "commit must use the proposal revision and idempotency key")
        proposal.status = "approval_required"
        result = proposal.public()
        self._by_task[proposal.task_id] = result
        self._by_key[proposal.idempotency_key] = (
            proposal.task_id, proposal.fingerprint, result)
        if self.tasks is not None:
            self.tasks.transition(proposal.task_id, "approval_required", result)
        return result

    def approve(self, task_id: str) -> dict:
        proposal = self._active
        if proposal is None or proposal.task_id != task_id:
            return self.preview(task_id)
        stale = self._stale(proposal)
        if stale:
            return stale
        if proposal.changes:
            before = len(self.history.undo_stack)
            self.history.execute(AIPropertyChangeCommand(
                proposal.changes, proposal.task_id))
            if self.history.last_error is not None or \
                    len(self.history.undo_stack) != before + 1:
                return _error("commit_failed", self.history.last_error or
                              "the history command was not recorded")
        result = proposal.public()
        result.update({"status": "committed", "changed": bool(proposal.changes),
                       "content_revision": self.scene.content_version,
                       "requires_user_approval": False})
        proposal.status = "committed"
        self._by_task[proposal.task_id] = result
        self._by_key[proposal.idempotency_key] = (
            proposal.task_id, proposal.fingerprint, result)
        self._active = None
        if self.tasks is not None:
            self.tasks.transition(proposal.task_id, "committed", result)
        return dict(result)

    def discard(self, task_id="") -> dict:
        task_id = str(task_id or "")
        proposal = self._active
        if proposal is None or proposal.task_id != task_id:
            return self.preview(task_id)
        result = {"ok": True, "task_id": task_id, "status": "discarded",
                  "changed": False, "content_revision": self.scene.content_version}
        proposal.status = "discarded"
        self._by_task[task_id] = result
        self._by_key[proposal.idempotency_key] = (
            proposal.task_id, proposal.fingerprint, result)
        self._active = None
        if self.tasks is not None:
            self.tasks.transition(task_id, "discarded", result)
        return dict(result)
