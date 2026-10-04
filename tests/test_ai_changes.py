# SPDX-License-Identifier: GPL-3.0-or-later
"""Preview-first typed AI changes and their document safety contract."""
from __future__ import annotations

from core.ai_changes import AIChangeService
from core.group import Group
from core.history import History
from core.layers import Layer
from core.mesh import Mesh
from core.scene import Scene


def _model():
    scene = Scene()
    scene.layers.append(Layer("Furniture"))
    chair = Group(Mesh(), "Chair")
    table = Group(Mesh(), "Table")
    scene.groups.extend([chair, table])
    history = History(scene)
    return scene, history, chair, table, AIChangeService(scene, history)


def _proposal(scene, chair, table):
    return {
        "task_id": "tidy-dining",
        "intent": "organise the dining furniture",
        "base_revision": scene.content_version,
        "idempotency_key": "tidy-dining-001",
        "actions": [
            {"action": "rename_entities", "entity_ids": [chair.uid],
             "name": "Dining chair"},
            {"action": "assign_tag", "entity_ids": [chair.uid, table.uid],
             "tag": "Furniture"},
            {"action": "set_visibility", "entity_ids": [table.uid],
             "visible": False},
            {"action": "set_lock", "entity_ids": [chair.uid],
             "locked": True},
        ],
    }


def test_preview_is_pure_and_user_approval_commits_one_undo_step():
    scene, history, chair, table, service = _model()
    args = _proposal(scene, chair, table)
    before_revision = scene.content_version

    preview = service.propose(**args)
    assert preview["ok"] and preview["status"] == "preview_ready"
    assert len(preview["changes"]) == 5
    assert preview["requires_user_approval"] is True
    assert (chair.name, chair.layer, chair.locked, table.hidden) == \
        ("Chair", None, False, False)
    assert scene.content_version == before_revision
    assert history.undo_stack == []

    requested = service.request_commit(
        args["task_id"], args["base_revision"], args["idempotency_key"])
    assert requested["status"] == "approval_required"
    assert chair.name == "Chair"                       # still preview-only

    committed = service.approve(args["task_id"])
    assert committed["status"] == "committed" and committed["changed"]
    assert (chair.name, chair.layer, chair.locked, table.layer, table.hidden) == \
        ("Dining chair", "Furniture", True, "Furniture", True)
    assert len(history.undo_stack) == 1

    assert history.undo()
    assert (chair.name, chair.layer, chair.locked, table.layer, table.hidden) == \
        ("Chair", None, False, None, False)
    assert history.redo()
    assert (chair.name, chair.layer, chair.locked, table.layer, table.hidden) == \
        ("Dining chair", "Furniture", True, "Furniture", True)


def test_idempotency_never_duplicates_a_commit_and_conflicts_fail():
    scene, history, chair, table, service = _model()
    args = _proposal(scene, chair, table)
    first = service.propose(**args)
    assert service.propose(**args) == first
    service.request_commit(args["task_id"], args["base_revision"],
                           args["idempotency_key"])
    committed = service.approve(args["task_id"])

    # Retrying the original request returns its terminal result and creates
    # neither a second command nor a second edit.
    assert service.propose(**args)["status"] == "committed"
    assert len(history.undo_stack) == 1
    changed = dict(args)
    changed["intent"] = "different work"
    assert service.propose(**changed)["code"] == "idempotency_conflict"
    assert committed["content_revision"] == scene.content_version


def test_stale_preview_releases_lease_and_discard_never_changes_document():
    scene, history, chair, table, service = _model()
    args = _proposal(scene, chair, table)
    service.propose(**args)
    scene.version += 1                              # a manual user edit
    stale = service.validate(args["task_id"])
    assert stale["code"] == "stale_revision"
    assert service.summary() is None
    assert history.undo_stack == [] and chair.name == "Chair"

    next_args = dict(args, task_id="next-task", idempotency_key="next-task-001",
                     base_revision=scene.content_version)
    assert service.propose(**next_args)["ok"]
    discarded = service.discard("next-task")
    assert discarded["status"] == "discarded" and not discarded["changed"]
    assert service.summary() is None and chair.name == "Chair"


def test_invalid_locked_missing_tag_and_busy_proposals_are_rejected():
    scene, _history, chair, table, service = _model()
    chair.locked = True
    base = scene.content_version
    locked = service.propose(
        "locked", "rename", base, "locked-key-001",
        [{"action": "rename_entities", "entity_ids": [chair.uid],
          "name": "No"}])
    assert locked["code"] == "entity_locked"
    missing = service.propose(
        "missing", "tag", base, "missing-key-001",
        [{"action": "assign_tag", "entity_ids": [table.uid],
          "tag": "Does not exist"}])
    assert missing["code"] == "unknown_tag"

    unlock = service.propose(
        "unlock", "unlock", base, "unlock-key-001",
        [{"action": "set_lock", "entity_ids": [chair.uid],
          "locked": False}])
    assert unlock["ok"]
    busy = service.propose(
        "other", "hide", base, "other-key-001",
        [{"action": "set_visibility", "entity_ids": [table.uid],
          "visible": False}])
    assert busy["code"] == "busy" and busy["task_id"] == "unlock"
