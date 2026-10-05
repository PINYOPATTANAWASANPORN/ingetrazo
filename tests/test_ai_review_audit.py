# SPDX-License-Identifier: GPL-3.0-or-later
"""Audit events must survive report invalidation and expose no reviewer text."""
import hashlib
import json

from core.ai_review_audit import GENESIS, ReviewAuditTrail
from core.ai_review_export import canonical
from core.ai_external_review import ExternalReviewService
from core.ai_tasks import AITaskService
from core.scene import Scene


def _submit(service, begun, assignment, result):
    return service.submit(begun["review_id"], assignment["role"],
                          assignment["submission_token"], begun["snapshot_id"], result)


def test_completed_retry_then_stale_has_two_chained_events_without_prose():
    scene = Scene()
    tasks = AITaskService(scene)
    task = tasks.create("ตรวจสอบ", execution="analysis_only")
    service = ExternalReviewService(scene, tasks)
    begun = service.begin(task["task_id"])
    answer = {"summary": "Sensitive project description", "findings": []}
    for assignment in begun["assignments"]:
        _submit(service, begun, assignment, answer)
    _submit(service, begun, begun["assignments"][0], answer)  # identical retry
    first_page = tasks.review_audit(limit=1)
    assert first_page["total_events"] == 1
    assert first_page["has_more"] is False
    scene.version += 1
    assert service.get(begun["review_id"])["status"] == "stale"
    assert tasks.get(task["task_id"])["review"]["status"] == "stale"
    trail = tasks.review_audit()
    assert [event["status"] for event in trail["events"]] == ["completed", "stale"]
    assert trail["head_digest"] == trail["events"][-1]["digest"]
    assert trail["events"][0]["previous_digest"] == GENESIS
    assert trail["events"][1]["previous_digest"] == trail["events"][0]["digest"]
    for event in trail["events"]:
        digest = event["digest"]
        assert hashlib.sha256(canonical({k: v for k, v in event.items()
                                         if k != "digest"})).hexdigest() == digest
    serialized = json.dumps(trail)
    assert "Sensitive project description" not in serialized
    assert all(a["submission_token"] not in serialized for a in begun["assignments"])
    trail["events"][0]["status"] = "tampered"
    assert tasks.review_audit()["events"][0]["status"] == "completed"
    assert tasks.review_audit(after_sequence=1, limit=1)["events"][0]["status"] == "stale"


def test_audit_pagination_rejects_invalid_inputs_and_is_scene_scoped():
    ledger = ReviewAuditTrail()
    for after, limit in [(-1, 1), (0, 0), (0, 101), (1, 1), (True, 1), (0, 1.5)]:
        assert ledger.page(after, limit)["code"] == "invalid_audit_page"
    assert ledger.page()["events"] == []
    assert AITaskService(Scene()).review_audit()["head_digest"] == GENESIS
