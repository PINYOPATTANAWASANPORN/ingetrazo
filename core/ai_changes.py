# SPDX-License-Identifier: GPL-3.0-or-later
"""Validated, preview-first AI changes for stable model containers.

This first typed-write slice deliberately changes only group/component
properties.  A proposal is pure data until the user approves it in an
IngeTrazo AI panel.  Commit rechecks the content revision and records the
complete change set as one history command.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass

from PySide6.QtGui import QMatrix4x4, QVector3D

from core.history import (Command, MoveGroupCommand, RotateGroupCommand,
                          ScaleGroupCommand, rotation_matrix, scale_matrix)
from core.layers import DEFAULT_LAYER

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
        normalised: list[dict] = []
        changes: dict[tuple[str, str], dict] = {}
        transformed: set[str] = set()
        total_entities = 0
        for index, raw in enumerate(actions):
            if not isinstance(raw, dict):
                return _error("invalid_action", f"action {index} must be an object")
            kind = str(raw.get("action") or "")
            field = ACTION_FIELDS.get(kind)
            if field is None and kind != TRANSFORM_ACTION:
                return _error("unsupported_action", f"unsupported action {kind!r}")
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
