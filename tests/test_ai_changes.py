# SPDX-License-Identifier: GPL-3.0-or-later
"""Preview-first typed AI changes and their document safety contract."""
from __future__ import annotations

from core.ai_changes import AIChangeService
from core.group import Group
from core.history import History
from core.layers import Layer
from core.materials import Material
from core.mesh import Mesh
from core.scene import Scene
from PySide6.QtGui import QMatrix4x4, QVector3D


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


def _solid_group(name="Box"):
    mesh = Mesh()
    mesh.add_face([QVector3D(0, 0, 0), QVector3D(2, 0, 0),
                   QVector3D(2, 1, 0), QVector3D(0, 1, 0)])
    return Group(mesh, name)


def test_material_and_translation_preview_commit_as_one_undo_step():
    scene = Scene()
    scene.materials["Oak"] = Material("Oak", color=(0.5, 0.3, 0.1))
    box = _solid_group()
    scene.groups.append(box)
    history = History(scene)
    service = AIChangeService(scene, history)
    args = {
        "task_id": "place-oak-box",
        "intent": "paint and move the box",
        "base_revision": scene.content_version,
        "idempotency_key": "place-oak-box-001",
        "actions": [
            {"action": "assign_material", "entity_ids": [box.uid],
             "material": "Oak"},
            {"action": "transform_entities", "entity_ids": [box.uid],
             "operation": "translate", "delta": [3, 4, 5]},
        ],
    }

    preview = service.propose(**args)
    assert preview["ok"] and len(preview["changes"]) == 2
    transform = next(change for change in preview["changes"]
                     if change["field"] == "translate")
    assert transform["before"]["bounds"]["min"] == [0.0, 0.0, 0.0]
    assert transform["after"]["bounds"]["min"] == [3.0, 4.0, 5.0]
    assert box.material is None
    assert box.mesh.vertices[0].position.z() == 0.0

    service.request_commit(args["task_id"], args["base_revision"],
                           args["idempotency_key"])
    result = service.approve(args["task_id"])
    assert result["status"] == "committed" and len(history.undo_stack) == 1
    assert box.material["mat"] == "Oak"
    assert min(v.position.x() for v in box.mesh.vertices) == 3.0
    assert min(v.position.z() for v in box.mesh.vertices) == 5.0

    assert history.undo()
    assert box.material is None
    assert min(v.position.x() for v in box.mesh.vertices) == 0.0
    assert history.redo()
    assert box.material["mat"] == "Oak"
    assert min(v.position.y() for v in box.mesh.vertices) == 4.0


def test_typed_box_and_cylinder_creation_preview_and_commit_as_one_undo():
    from core.orient import is_closed

    scene = Scene()
    scene.layers.append(Layer("Masses"))
    scene.materials["Concrete"] = Material(
        "Concrete", color=(0.6, 0.6, 0.6))
    history = History(scene)
    service = AIChangeService(scene, history)
    args = {
        "task_id": "create-masses",
        "intent": "create a box and a column",
        "base_revision": scene.content_version,
        "idempotency_key": "create-masses-001",
        "actions": [
            {"action": "create_box", "name": "Podium",
             "origin": [1, 2, 0], "size": [4, 3, 0.5],
             "tag": "Masses", "material": "Concrete"},
            {"action": "create_cylinder", "name": "Column",
             "origin": [3, 3, 0.5], "radius": 0.25, "height": 3,
             "segments": 16, "tag": "Masses", "component": True},
        ],
    }

    preview = service.propose(**args)
    assert preview["ok"] and preview["status"] == "preview_ready"
    assert len(preview["changes"]) == 2
    assert scene.groups == [] and history.undo_stack == []
    box_preview, cylinder_preview = preview["changes"]
    assert box_preview["field"] == "created"
    assert box_preview["after"]["bounds"]["min"] == [1.0, 2.0, 0.0]
    assert box_preview["after"]["bounds"]["size"] == [4.0, 3.0, 0.5]
    assert cylinder_preview["entity_type"] == "component"
    assert cylinder_preview["after"]["bounds"]["min"] == [2.75, 2.75, 0.5]

    service.request_commit(args["task_id"], args["base_revision"],
                           args["idempotency_key"])
    committed = service.approve(args["task_id"])
    assert committed["status"] == "committed"
    assert len(scene.groups) == 2 and len(history.undo_stack) == 1
    podium, column = scene.groups
    assert podium.name == "Podium" and podium.layer == "Masses"
    assert podium.material["mat"] == "Concrete"
    assert column.name == "Column" and column.is_component()
    assert all(is_closed(group.mesh) for group in scene.groups)
    assert history.undo() and scene.groups == []
    assert history.redo() and [group.name for group in scene.groups] == [
        "Podium", "Column"]


def test_typed_creation_rejects_invalid_or_nested_geometry():
    scene, _history, chair, _table, service = _model()
    base = scene.content_version
    invalid = service.propose(
        "bad-box", "create", base, "bad-box-key-001",
        [{"action": "create_box", "name": "Bad", "size": [1, 0, 2]}])
    assert invalid["code"] == "invalid_size"

    scene.edit_group = chair
    nested = service.propose(
        "nested-box", "create", base, "nested-box-key-001",
        [{"action": "create_box", "name": "Nested", "size": [1, 1, 1]}])
    assert nested["code"] == "nested_creation_unsupported"
    assert len(scene.groups) == 2


def test_rotation_and_non_uniform_scale_have_exact_preview_and_redo():
    for operation, parameters, expected_size in (
            ("rotate", {"center": [0, 0, 0], "axis": [0, 0, 1],
                        "degrees": 90}, [1.0, 2.0, 0.0]),
            ("scale", {"center": [0, 0, 0], "factor": [2, 3, 1]},
             [4.0, 3.0, 0.0])):
        scene = Scene()
        box = _solid_group()
        scene.groups.append(box)
        history = History(scene)
        service = AIChangeService(scene, history)
        args = {
            "task_id": f"{operation}-box",
            "intent": operation,
            "base_revision": scene.content_version,
            "idempotency_key": f"{operation}-box-001",
            "actions": [{"action": "transform_entities",
                         "entity_ids": [box.uid], "operation": operation,
                         **parameters}],
        }
        preview = service.propose(**args)
        size = preview["changes"][0]["after"]["bounds"]["size"]
        assert size == expected_size
        service.request_commit(args["task_id"], args["base_revision"],
                               args["idempotency_key"])
        assert service.approve(args["task_id"])["status"] == "committed"
        applied = [(v.position.x(), v.position.y(), v.position.z())
                   for v in box.mesh.vertices]
        assert history.undo()
        assert history.redo()
        assert [(v.position.x(), v.position.y(), v.position.z())
                for v in box.mesh.vertices] == applied


def test_transform_and_material_validation_rejects_ambiguous_changes():
    scene = Scene()
    parent = Group(name="Parent")
    child = Group(name="Child")
    parent.adopt([child])
    box = _solid_group()
    scene.groups.extend([parent, box])
    service = AIChangeService(scene, History(scene))
    base = scene.content_version

    missing = service.propose(
        "missing-material", "paint", base, "missing-material-001",
        [{"action": "assign_material", "entity_ids": [box.uid],
          "material": "Absent"}])
    assert missing["code"] == "unknown_material"
    nested = service.propose(
        "nested", "move", base, "nested-transform-001",
        [{"action": "transform_entities", "entity_ids": [child.uid],
          "operation": "translate", "delta": [1, 0, 0]}])
    assert nested["code"] == "nested_transform_unsupported"
    zero = service.propose(
        "zero", "scale", base, "zero-scale-001",
        [{"action": "transform_entities", "entity_ids": [box.uid],
          "operation": "scale", "center": [0, 0, 0], "factor": 0}])
    assert zero["code"] == "invalid_transform"
    duplicate = service.propose(
        "twice", "move twice", base, "duplicate-transform-001",
        [{"action": "transform_entities", "entity_ids": [box.uid],
          "operation": "translate", "delta": [1, 0, 0]},
         {"action": "transform_entities", "entity_ids": [box.uid],
          "operation": "translate", "delta": [0, 1, 0]}])
    assert duplicate["code"] == "duplicate_transform"


def test_component_transform_moves_only_the_instance_and_no_op_is_empty():
    scene = Scene()
    prototype = _solid_group().mesh
    first, sibling = Group(prototype, "First"), Group(prototype, "Sibling")
    first.xform, sibling.xform = QMatrix4x4(), QMatrix4x4()
    scene.groups.extend([first, sibling])
    history = History(scene)
    service = AIChangeService(scene, history)
    base = scene.content_version
    no_op = service.propose(
        "no-op", "leave in place", base, "no-op-transform-001",
        [{"action": "transform_entities", "entity_ids": [first.uid],
          "operation": "translate", "delta": [0, 0, 0]}])
    assert no_op["ok"] and no_op["changes"] == []
    service.discard("no-op")

    args = {
        "task_id": "move-instance", "intent": "move one component",
        "base_revision": scene.content_version,
        "idempotency_key": "move-instance-001",
        "actions": [{"action": "transform_entities",
                     "entity_ids": [first.uid], "operation": "translate",
                     "delta": [7, 0, 0]}],
    }
    service.propose(**args)
    service.request_commit(args["task_id"], args["base_revision"],
                           args["idempotency_key"])
    service.approve(args["task_id"])
    assert first.mesh is sibling.mesh is prototype
    assert first.xform.map(QVector3D()).x() == 7.0
    assert sibling.xform.map(QVector3D()).x() == 0.0
    assert min(vertex.position.x() for vertex in prototype.vertices) == 0.0
    assert history.undo()
    assert first.xform.map(QVector3D()).x() == 0.0
