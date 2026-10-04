# SPDX-License-Identifier: GPL-3.0-or-later
"""Validated, preview-first AI changes for stable model containers.

This first typed-write slice deliberately changes only group/component
properties.  A proposal is pure data until the user approves it in the AI
bridge panel.  Commit rechecks the content revision and records the complete
change set as one history command.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from core.history import Command
from core.layers import DEFAULT_LAYER

MAX_ACTIONS = 100
MAX_ENTITIES = 200
MAX_NAME = 200

ACTION_FIELDS = {
    "rename_entities": "name",
    "set_visibility": "hidden",
    "set_lock": "locked",
    "assign_tag": "layer",
}


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
        group = change["_entity"]
        field = change["field"]
        if field == "layer":
            group.layer = None if value == DEFAULT_LAYER else value
        else:
            setattr(group, field, value)

    def _apply(self, scene, side: str) -> None:
        for change in self.changes:
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

    def __init__(self, scene, history) -> None:
        self.scene = scene
        self.history = history
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
        total_entities = 0
        for index, raw in enumerate(actions):
            if not isinstance(raw, dict):
                return _error("invalid_action", f"action {index} must be an object")
            kind = str(raw.get("action") or "")
            field = ACTION_FIELDS.get(kind)
            if field is None:
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
            else:
                value = str(raw.get("tag") or "").strip()
                layer = self.scene.layer(value)
                if layer is None:
                    return _error("unknown_tag", f"tag {value!r} does not exist")
                if not layer.visible or layer.locked:
                    return _error("unavailable_tag",
                                  f"tag {value!r} is hidden or locked")

            entry = {"action": kind, "entity_ids": ids}
            entry[{"name": "name", "hidden": "visible",
                   "locked": "locked", "layer": "tag"}[field]] = (
                       not value if field == "hidden" else value)
            normalised.append(entry)
            for uid in ids:
                group = groups[uid]
                if group.locked and field != "locked":
                    return _error("entity_locked",
                                  f"entity {uid} is locked", entity_id=uid)
                before = (getattr(group, field) if field != "layer" else
                          (getattr(group, "layer", None) or DEFAULT_LAYER))
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
        fingerprint = self._fingerprint(str(intent or ""), base, actions)
        prior = self._by_key.get(key)
        if prior is not None:
            prior_task, prior_fingerprint, result = prior
            if prior_task != task_id or prior_fingerprint != fingerprint:
                return _error("idempotency_conflict",
                              "idempotency_key was already used for different input")
            return dict(result)
        if self._active is not None and self._active.task_id != task_id:
            return _error("busy", "another AI change set holds the write lease",
                          task_id=self._active.task_id)
        if base != self.scene.content_version:
            return _error("stale_revision", "base_revision is not current",
                          content_revision=self.scene.content_version)
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
        return dict(result)
