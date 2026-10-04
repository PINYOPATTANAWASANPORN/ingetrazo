# SPDX-License-Identifier: GPL-3.0-or-later
"""Document-scoped AI tasks assembled from short user intent.

The task service turns a compact request into a bounded contract before any
agent proposes writes.  It resolves the live scope once, pins the document
revision, records visible assumptions and acceptance criteria, and provides a
small deterministic plan.  Model providers may refine that plan later, but
they cannot silently widen its entity scope.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field


SCHEMA_VERSION = "1.0"
MAX_TEXT = 1000
MAX_LIST = 20
MAX_METADATA_BYTES = 8192
MAX_SCOPE_IDS = 200
EXECUTION_MODES = {"analysis_only", "preview_first", "apply_safe_changes"}
GOALS = {"create", "revise", "furnish", "check", "quantify", "explain"}


def _error(code: str, message: str, **extra) -> dict:
    return {"ok": False, "code": code, "message": message, **extra}


def _strings(value, label: str) -> list[str] | dict:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > MAX_LIST:
        return _error("invalid_task", f"{label} must be an array of at most {MAX_LIST} strings")
    out = []
    for item in value:
        text = str(item).strip()
        if not text or len(text) > 500:
            return _error("invalid_task", f"each {label} item must contain 1-500 characters")
        out.append(text)
    return out


def _json_value(value, label: str):
    value = {} if value is None else value
    try:
        raw = json.dumps(value, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):
        return _error("invalid_task", f"{label} must be JSON-compatible")
    if len(raw.encode()) > MAX_METADATA_BYTES:
        return _error("invalid_task", f"{label} exceeds {MAX_METADATA_BYTES} bytes")
    return json.loads(raw)


def _goal(intent: str, requested: str) -> str:
    requested = str(requested or "").strip().lower()
    if requested:
        return requested if requested in GOALS else ""
    text = intent.casefold()
    rules = (
        ("quantify", ("count", "quantity", "area", "volume", "นับ", "ปริมาณ")),
        ("check", ("check", "validate", "inspect", "ตรวจ", "เช็ค")),
        ("explain", ("explain", "describe", "what", "อธิบาย", "คืออะไร")),
        ("furnish", ("furnish", "furniture", "จัดเฟอร์นิเจอร์", "ตกแต่ง")),
        ("create", ("create", "add", "draw", "make", "สร้าง", "เพิ่ม", "วาด")),
    )
    for goal, words in rules:
        if any(word in text for word in words):
            return goal
    return "revise"


@dataclass
class _Task:
    task_id: str
    intent: str
    goal: str
    execution: str
    base_revision: int
    scope: dict
    allowed_ids: set[str]
    constraints: object
    assumptions: list[str]
    acceptance_criteria: list[str]
    plan: list[dict]
    status: str = "ready"
    warnings: list[str] = field(default_factory=list)
    result: dict | None = None

    def public(self, content_revision: int) -> dict:
        return {
            "ok": True,
            "schema_version": SCHEMA_VERSION,
            "task_id": self.task_id,
            "status": self.status,
            "intent": self.intent,
            "goal": self.goal,
            "execution": self.execution,
            "base_revision": self.base_revision,
            "content_revision": content_revision,
            "stale": (self.status not in {"committed", "discarded"}
                      and content_revision != self.base_revision),
            "scope": self.scope,
            "constraints": self.constraints,
            "assumptions": list(self.assumptions),
            "acceptance_criteria": list(self.acceptance_criteria),
            "plan": list(self.plan),
            "warnings": list(self.warnings),
            "result": self.result,
        }


class AITaskService:
    """Session task registry for one live document."""

    def __init__(self, scene) -> None:
        self.scene = scene
        self._tasks: dict[str, _Task] = {}
        self._active_id: str | None = None

    def _scope(self, requested) -> dict:
        groups = self.scene.groups_by_uid()
        selected = {id(entity) for entity in self.scene.selection}
        selected_ids = [uid for uid, group in groups.items()
                        if id(group) in selected]
        warning = None

        if isinstance(requested, dict):
            if requested.get("kind") != "entities":
                return _error("invalid_scope", "explicit scope kind must be entities")
            raw = requested.get("entity_ids")
            if not isinstance(raw, list) or not raw:
                return _error("invalid_scope", "entity scope needs entity_ids")
            entity_ids = list(dict.fromkeys(str(item) for item in raw))
            if len(entity_ids) > MAX_SCOPE_IDS:
                return _error("scope_too_large",
                              f"explicit scope accepts at most {MAX_SCOPE_IDS} entity IDs")
            missing = [uid for uid in entity_ids if uid not in groups]
            if missing:
                return _error("unknown_entity", "scope contains unknown entities",
                              entity_ids=missing)
            return {"kind": "entities", "entity_ids": entity_ids,
                    "entity_count": len(entity_ids),
                    "_allowed_ids": entity_ids}

        kind = str(requested or "auto").strip().lower()
        if kind == "auto":
            if selected_ids:
                kind = "selection"
            elif self.scene.edit_group is not None:
                kind = "current_group"
            else:
                kind = "visible_model"
        if kind == "selection":
            if not selected_ids:
                return _error("empty_scope", "selection contains no stable group or component")
            entity_ids = selected_ids
        elif kind == "current_group":
            root = self.scene.edit_group
            if root is None:
                return _error("empty_scope", "no group is currently open for editing")
            entity_ids = []

            def walk(group):
                if group.uid not in entity_ids:
                    entity_ids.append(group.uid)
                for child in getattr(group, "children", ()):
                    walk(child)

            walk(root)
        elif kind == "visible_model":
            entity_ids = [uid for uid, group in groups.items()
                          if self.scene.entity_visible(group)]
        elif kind == "whole_model":
            entity_ids = list(groups)
        else:
            return _error("invalid_scope",
                          "scope must be auto, selection, current_group, visible_model, whole_model, or entities")
        result = {"kind": kind, "entity_ids": entity_ids[:MAX_SCOPE_IDS],
                  "entity_count": len(entity_ids),
                  "truncated": len(entity_ids) > MAX_SCOPE_IDS,
                  "_allowed_ids": entity_ids}
        if warning:
            result["warning"] = warning
        return result

    @staticmethod
    def _plan(goal: str, execution: str) -> list[dict]:
        read_only = execution == "analysis_only" or goal in {"check", "quantify", "explain"}
        steps = [{"step": "inspect_scope", "role": "coordinator",
                  "mode": "read"}]
        if read_only:
            steps.append({"step": goal, "role": "specialist", "mode": "read"})
            steps.append({"step": "report", "role": "coordinator", "mode": "read"})
        else:
            steps.extend([
                {"step": "propose_actions", "role": "modeler", "mode": "prepare"},
                {"step": "validate", "role": "validator", "mode": "read"},
                {"step": "request_user_approval", "role": "coordinator",
                 "mode": "commit_request"},
            ])
        return steps

    def create(self, intent="", scope="auto", goal="", constraints=None,
               execution="preview_first", assumptions=None,
               acceptance_criteria=None) -> dict:
        intent = str(intent or "").strip()
        if not intent or len(intent) > MAX_TEXT:
            return _error("invalid_intent", f"intent must contain 1-{MAX_TEXT} characters")
        execution = str(execution or "preview_first").strip().lower()
        if execution not in EXECUTION_MODES:
            return _error("invalid_execution", "unsupported execution mode")
        classified = _goal(intent, goal)
        if not classified:
            return _error("invalid_goal", f"goal must be one of {sorted(GOALS)}")
        resolved = self._scope(scope)
        if not resolved.get("kind"):
            return resolved
        constraints = _json_value(constraints, "constraints")
        if isinstance(constraints, dict) and constraints.get("code") == "invalid_task":
            return constraints
        assumptions = _strings(assumptions, "assumptions")
        if isinstance(assumptions, dict):
            return assumptions
        criteria = _strings(acceptance_criteria, "acceptance_criteria")
        if isinstance(criteria, dict):
            return criteria
        task_id = "task-" + uuid.uuid4().hex[:16]
        allowed_ids = set(resolved.pop("_allowed_ids"))
        if not resolved.get("truncated"):
            resolved.pop("truncated", None)
        task = _Task(
            task_id, intent, classified, execution,
            self.scene.content_version, resolved, allowed_ids,
            constraints, assumptions,
            criteria, self._plan(classified, execution))
        self._tasks[task_id] = task
        self._active_id = task_id
        return task.public(self.scene.content_version)

    def get(self, task_id="") -> dict:
        task = self._tasks.get(str(task_id or ""))
        if task is None:
            return _error("unknown_task", f"task {task_id!r} does not exist")
        return task.public(self.scene.content_version)

    def task(self, task_id: str) -> _Task | None:
        return self._tasks.get(str(task_id or ""))

    def summary(self) -> dict | None:
        task = self._tasks.get(self._active_id or "")
        if task is None:
            return None
        return {"task_id": task.task_id, "intent": task.intent,
                "status": task.status, "goal": task.goal,
                "scope_kind": task.scope["kind"],
                "scope_count": task.scope["entity_count"]}

    def validate_proposal(self, task_id, base_revision, actions) -> dict | None:
        task = self.task(task_id)
        if task is None:                         # legacy unregistered task
            return None
        if task.status not in {"ready", "preview_ready"}:
            return _error("invalid_task_state",
                          f"task is {task.status}, not ready for a proposal")
        if task.execution == "analysis_only" or task.goal in {
                "check", "quantify", "explain"}:
            return _error("task_read_only",
                          "this task is analysis-only and cannot propose writes")
        if base_revision != task.base_revision:
            return _error("task_revision_mismatch",
                          "proposal must use the task base revision",
                          base_revision=task.base_revision)
        allowed = task.allowed_ids
        requested = {str(uid) for action in actions if isinstance(action, dict)
                     for uid in (action.get("entity_ids") or [])}
        outside = sorted(requested - allowed)
        if outside:
            return _error("scope_violation",
                          "proposal references entities outside the task scope",
                          entity_ids=outside)
        return None

    def transition(self, task_id: str, status: str, result=None) -> None:
        task = self.task(task_id)
        if task is None:
            return
        task.status = status
        if result is not None:
            task.result = {key: value for key, value in result.items()
                           if key in {"changed", "content_revision", "validation",
                                      "affected_entities", "code", "message"}}

