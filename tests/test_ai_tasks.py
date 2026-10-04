# SPDX-License-Identifier: GPL-3.0-or-later
"""Short-intent AI tasks, bounded scope, and lifecycle integration."""
from __future__ import annotations

from core.ai_changes import AIChangeService
from core.ai_tasks import AITaskService
from core.group import Group
from core.history import History
from core.mesh import Mesh
from core.scene import Scene


def _scene():
    scene = Scene()
    chair = Group(Mesh(), "Chair")
    table = Group(Mesh(), "Table")
    hidden = Group(Mesh(), "Hidden")
    hidden.hidden = True
    scene.groups.extend([chair, table, hidden])
    return scene, chair, table, hidden


def test_short_intent_prefers_selection_and_builds_visible_plan():
    scene, chair, table, _hidden = _scene()
    scene.selection.add(chair)
    tasks = AITaskService(scene)

    result = tasks.create(
        "จัดเฟอร์นิเจอร์บริเวณนี้สำหรับหกคน",
        constraints={"seats": 6}, assumptions=["retain the table"],
        acceptance_criteria=["six usable seats"])

    assert result["ok"] and result["goal"] == "furnish"
    assert result["scope"] == {"kind": "selection",
                               "entity_ids": [chair.uid], "entity_count": 1}
    assert result["constraints"] == {"seats": 6}
    assert result["assumptions"] == ["retain the table"]
    assert [step["step"] for step in result["plan"]] == [
        "inspect_scope", "propose_actions", "validate",
        "request_user_approval"]
    assert table.uid not in result["scope"]["entity_ids"]
    assert scene.content_version == 0               # task creation is read-only


def test_auto_scope_falls_back_to_visible_model_and_analysis_stays_read_only():
    scene, chair, table, hidden = _scene()
    tasks = AITaskService(scene)
    result = tasks.create("ตรวจสอบโมเดล", execution="analysis_only")

    assert result["goal"] == "check"
    assert result["scope"]["kind"] == "visible_model"
    assert set(result["scope"]["entity_ids"]) == {chair.uid, table.uid}
    assert hidden.uid not in result["scope"]["entity_ids"]
    assert all(step["mode"] == "read" for step in result["plan"])
    service = AIChangeService(scene, History(scene), tasks)
    denied = service.propose(
        result["task_id"], "", result["base_revision"], "read-only-task-001",
        [{"action": "rename_entities", "entity_ids": [chair.uid],
          "name": "No write"}])
    assert denied["code"] == "task_read_only"


def test_explicit_scope_rejects_unknown_ids_and_metadata_is_bounded():
    scene, chair, _table, _hidden = _scene()
    tasks = AITaskService(scene)
    missing = tasks.create("rename", {"kind": "entities",
                                      "entity_ids": [chair.uid, "missing"]})
    assert missing["code"] == "unknown_entity"
    invalid_goal = tasks.create("rename", goal="teleport")
    assert invalid_goal["code"] == "invalid_goal"
    too_large = tasks.create("rename", constraints={"x": "a" * 9000})
    assert too_large["code"] == "invalid_task"


def test_large_model_scope_is_bounded_but_enforcement_keeps_full_scope():
    scene, _chair, _table, _hidden = _scene()
    extra = [Group(Mesh(), f"Group {index}") for index in range(210)]
    scene.groups.extend(extra)
    tasks = AITaskService(scene)
    task = tasks.create("rename one group", scope="whole_model")
    assert task["scope"]["truncated"] is True
    assert len(task["scope"]["entity_ids"]) == 200
    assert task["scope"]["entity_count"] == 213
    target = extra[-1]                         # omitted from the public page
    service = AIChangeService(scene, History(scene), tasks)
    allowed = service.propose(
        task["task_id"], "", task["base_revision"], "large-scope-task-001",
        [{"action": "rename_entities", "entity_ids": [target.uid],
          "name": "Still allowed"}])
    assert allowed["ok"] is True


def test_registered_task_enforces_scope_and_tracks_approval_lifecycle():
    scene, chair, table, _hidden = _scene()
    scene.selection.add(chair)
    tasks = AITaskService(scene)
    task = tasks.create("rename the selected chair")
    service = AIChangeService(scene, History(scene), tasks)

    outside = service.propose(
        task["task_id"], "", task["base_revision"], "outside-scope-001",
        [{"action": "rename_entities", "entity_ids": [table.uid],
          "name": "Dining table"}])
    assert outside["code"] == "scope_violation"
    assert tasks.get(task["task_id"])["status"] == "ready"

    args = {
        "task_id": task["task_id"], "intent": "",
        "base_revision": task["base_revision"],
        "idempotency_key": "rename-chair-001",
        "actions": [{"action": "rename_entities",
                     "entity_ids": [chair.uid], "name": "Dining chair"}],
    }
    assert service.propose(**args)["status"] == "preview_ready"
    assert tasks.get(task["task_id"])["status"] == "preview_ready"
    service.request_commit(task["task_id"], task["base_revision"],
                           args["idempotency_key"])
    assert tasks.get(task["task_id"])["status"] == "approval_required"
    committed = service.approve(task["task_id"])
    current = tasks.get(task["task_id"])
    assert current["status"] == "committed"
    assert current["result"]["changed"] is True
    assert committed["affected_entities"] == [chair.uid]
    assert chair.name == "Dining chair"


def test_document_change_marks_unproposed_task_stale():
    scene, chair, _table, _hidden = _scene()
    scene.selection.add(chair)
    tasks = AITaskService(scene)
    task = tasks.create("rename chair")
    scene.version += 1
    assert tasks.get(task["task_id"])["stale"] is True
    service = AIChangeService(scene, History(scene), tasks)
    stale = service.propose(
        task["task_id"], "", task["base_revision"], "stale-task-001",
        [{"action": "rename_entities", "entity_ids": [chair.uid],
          "name": "Old request"}])
    assert stale["code"] == "stale_revision"
    assert tasks.get(task["task_id"])["status"] == "stale"
