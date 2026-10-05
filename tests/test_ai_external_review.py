# SPDX-License-Identifier: GPL-3.0-or-later
import json
import pytest
from core.ai_changes import AIChangeService
from core.ai_external_review import ExternalReviewService, MAX_ACTIVE
from core.ai_tasks import AITaskService
from core.group import Group
from core.history import History
from core.scene import Scene


def setup():
    scene = Scene()
    group = Group(name="Selected")
    scene.groups.append(group)
    scene.selection.add(group)
    tasks = AITaskService(scene)
    task = tasks.create("review selection", execution="analysis_only")
    service = ExternalReviewService(scene, tasks)
    return scene, group, tasks, task, service


def submit(service, begun, index=0, verdict="concern", **overrides):
    assignment = begun["assignments"][index]
    args = dict(review_id=begun["review_id"], role=assignment["role"],
        submission_token=assignment["submission_token"], snapshot_id=begun["snapshot_id"],
        result={"summary": "Review", "findings": [{
            "entity_id": begun["snapshot"]["entities"][0]["id"],
            "topic": "material", "verdict": verdict, "evidence": "No named material."}]})
    args.update(overrides)
    return service.submit(**args)


def test_external_review_collects_conflicts_and_is_idempotent_without_history():
    scene, group, tasks, task, service = setup()
    history = History(scene)
    begun = service.begin(task["task_id"])
    assert service.begin(task["task_id"]) == begun
    assert submit(service, begun)["status"] == "collecting"
    assert submit(service, begun)["status"] == "collecting"
    assert submit(service, begun, verdict="clear")["code"] == "submission_conflict"
    result = submit(service, begun, 1, "clear")
    assert result["status"] == "completed"
    assert len(result["report"]["conflicts"]) == 1
    assert submit(service, begun, 1, "clear") == result
    assert tasks.get(task["task_id"])["review"] == result["report"]
    assert not history.undo_stack and group.name == "Selected"
    assert scene.content_version == task["base_revision"]
    serialized = json.dumps(service.get(begun["review_id"]))
    assert all(a["submission_token"] not in serialized for a in begun["assignments"])
    changes = AIChangeService(scene, history, tasks)
    assert not changes.propose(task["task_id"], "", scene.content_version, "write-attempt",
        [{"action": "rename_entities", "entity_ids": [group.uid], "name": "No"}])["ok"]


@pytest.mark.parametrize("override,code", [
    ({"submission_token": "wrong"}, "invalid_submission_token"),
    ({"submission_token": "ไทย"}, "invalid_submission_token"),
    ({"snapshot_id": "old"}, "snapshot_mismatch"),
    ({"role": "writer"}, "invalid_role"),
    ({"result": {"actions": []}}, "invalid_review_result"),
    ({"result": {"summary": "x", "findings": [{"entity_id": "outside", "topic": "tag",
       "verdict": "clear", "evidence": "x"}]}}, "invalid_review_result"),
])
def test_external_submission_rejects_unbound_or_unsafe_results(override, code):
    _scene, _group, _tasks, task, service = setup()
    begun = service.begin(task["task_id"])
    assert submit(service, begun, **override)["code"] == code
    assert not any(r["submitted"] for r in service.get(begun["review_id"])["roles"].values())


def test_role_tokens_cannot_be_swapped():
    _scene, _group, _tasks, task, service = setup()
    begun = service.begin(task["task_id"])
    assert submit(service, begun, submission_token=begun["assignments"][1]["submission_token"])["code"] == "invalid_submission_token"


@pytest.mark.parametrize("completed", [False, True])
def test_document_changes_invalidate_pending_and_completed_reviews(completed):
    scene, _group, tasks, task, service = setup()
    begun = service.begin(task["task_id"])
    submit(service, begun)
    if completed:
        submit(service, begun, 1)
    scene.version += 1
    result = service.get(begun["review_id"])
    assert result["status"] == "stale" and result["report"] is None
    assert submit(service, begun, 1)["code"] == "review_stale"
    assert tasks.get(task["task_id"])["review"]["status"] == "stale"


def test_cancel_rejects_late_submissions_and_preserves_document():
    scene, _group, tasks, task, service = setup()
    begun = service.begin(task["task_id"])
    result = service.cancel(begun["review_id"])
    assert result["status"] == "cancelled"
    assert service.cancel(begun["review_id"]) == result
    assert submit(service, begun)["code"] == "review_cancelled"
    assert tasks.get(task["task_id"])["status"] == "cancelled"
    assert [e["status"] for e in tasks.review_audit()["events"]] == ["cancelled"]
    assert scene.content_version == task["base_revision"]


def test_report_errors_produce_partial_and_active_sessions_are_bounded():
    _scene, _group, tasks, task, service = setup()
    begun = service.begin(task["task_id"])
    submit(service, begun)
    assert submit(service, begun, 1, result={"error": "provider unavailable"})["status"] == "partial"
    assert [e["status"] for e in tasks.review_audit()["events"]] == ["partial"]
    active = []
    for _ in range(MAX_ACTIVE):
        other = tasks.create("review", execution="analysis_only")
        active.append(service.begin(other["task_id"]))
    extra = tasks.create("review", execution="analysis_only")
    assert service.begin(extra["task_id"])["code"] == "review_limit"
    service.cancel(active[0]["review_id"])
    assert service.begin(extra["task_id"])["ok"]


def test_only_analysis_tasks_and_detached_packets_are_accepted():
    _scene, group, tasks, task, service = setup()
    writable = tasks.create("create something")
    assert service.begin(writable["task_id"])["code"] == "invalid_review_scope"
    begun = service.begin(task["task_id"])
    begun["snapshot"]["entities"][0]["name"] = "tampered"
    assert service.begin(task["task_id"])["snapshot"]["entities"][0]["name"] == group.name


def test_retention_evicts_terminal_snapshot_and_task_report(monkeypatch):
    import core.ai_external_review as module
    monkeypatch.setattr(module, "MAX_RETAINED", 2)
    _scene, _group, tasks, task, service = setup()
    first = service.begin(task["task_id"])
    submit(service, first)
    submit(service, first, 1)
    for _ in range(2):
        other = tasks.create("review", execution="analysis_only")
        begun = service.begin(other["task_id"])
        service.cancel(begun["review_id"])
    assert len(service.reviews) == 2
    assert service.get(first["review_id"])["code"] == "unknown_review"
    assert tasks.get(task["task_id"])["review"] is None
