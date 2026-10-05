# SPDX-License-Identifier: GPL-3.0-or-later
"""Architectural geometry, pure previews, scoped placement and history."""
import pytest
from PySide6.QtGui import QMatrix4x4, QVector3D

from core.ai_changes import AIChangeService
from core.ai_tasks import AITaskService
from core.group import Group
from core.history import History
from core.orient import is_closed, signed_volume
from core.scene import Scene


def setup():
    scene = Scene()
    history = History(scene)
    return scene, history, AIChangeService(scene, history)


def propose(scene, service, actions):
    return service.propose("architecture", "create", scene.content_version,
                           "architecture-001", actions)


def wall(**kwargs):
    return dict(action="create_wall", name="Wall", start=[0, 0, 0],
                end=[6, 0, 0], height=3, thickness=0.2, **kwargs)


def container(name="Storey"):
    group = Group(name=name)
    group.xform = QMatrix4x4()
    group.component = False
    return group


def test_wall_openings_and_slab_are_closed_outward_solids_and_one_undo():
    scene, history, service = setup()
    openings = [dict(offset=1, sill=0, width=1, height=2),
                dict(offset=3, sill=1, width=2, height=1)]
    result = propose(scene, service, [wall(openings=openings),
        dict(action="create_slab", name="Slab", origin=[0, 0, -0.25],
             size=[6, 4, 0.25])])
    assert result["ok"], result
    assert scene.groups == [] and not history.undo_stack
    service.approve("architecture")
    assert len(history.undo_stack) == 1
    assert all(is_closed(g.mesh) for g in scene.groups)
    assert all(len(e.faces) == 2 for g in scene.groups for e in g.mesh.edges)
    assert signed_volume(scene.groups[0].mesh) == pytest.approx((18 - 4) * .2)
    assert signed_volume(scene.groups[1].mesh) == pytest.approx(6)
    ids = [g.uid for g in scene.groups]
    assert history.undo() and not scene.groups
    assert history.redo() and [g.uid for g in scene.groups] == ids


@pytest.mark.parametrize("openings", [
    [dict(offset=1, sill=0, width=1, height=3)],
    [dict(offset=0, sill=1, width=1, height=1)],
    [dict(offset=1, sill=-1, width=1, height=1)],
    [dict(offset=1, sill=0, width=2, height=2),
     dict(offset=2, sill=1, width=1, height=1)],
    [dict(offset=1, sill=0, width=float("nan"), height=1)],
])
def test_invalid_openings_leave_no_preview_or_geometry(openings):
    scene, history, service = setup()
    result = propose(scene, service, [wall(openings=openings)])
    assert result["code"] == "invalid_openings"
    assert not scene.groups and not history.undo_stack and service.summary() is None


def test_parent_coordinates_match_world_preview_and_undo():
    scene, history, service = setup()
    root, parent = container("Building"), container()
    root.xform.translate(10, 20, 0)
    root.xform.rotate(90, 0, 0, 1)
    parent.xform.translate(2, 0, 3)
    root.children.append(parent)
    scene.groups.append(root)
    action = dict(action="create_slab", name="Floor", origin=[1, 0, 0],
                  size=[4, 2, .25], coordinate_space="parent", parent_id=parent.uid)
    result = propose(scene, service, [action])
    assert result["ok"], result
    bounds = result["changes"][0]["after"]["bounds"]
    assert bounds["min"] == pytest.approx([8, 23, 3])
    assert bounds["max"] == pytest.approx([10, 27, 3.25])
    assert not parent.children
    service.approve("architecture")
    child = parent.children[0]
    assert child not in scene.groups and not child.is_component()
    assert history.undo() and not parent.children
    assert history.redo() and parent.children == [child]


def test_parent_reference_and_root_creation_cannot_escape_entity_scope():
    scene, history, _service = setup()
    parent, outside = container(), container("Outside")
    scene.groups.extend([parent, outside])
    scene.selection.add(parent)
    tasks = AITaskService(scene)
    task = tasks.create("create floor")
    service = AIChangeService(scene, history, tasks)
    action = dict(action="create_slab", name="Floor", origin=[0, 0, 0], size=[2, 2, .2])
    def submit(value, key):
        return service.propose(task["task_id"], "", task["base_revision"], key, [value])
    assert submit(action, "root-escape-001")["code"] == "scope_violation"
    action.update(coordinate_space="parent", parent_id=outside.uid)
    assert submit(action, "parent-escape-001")["code"] == "scope_violation"
    action["parent_id"] = parent.uid
    assert submit(action, "parent-valid-001")["ok"]


@pytest.mark.parametrize("reason", ["space", "locked", "ancestor", "shared"])
def test_parent_contract_rejects_ambiguous_or_unavailable_targets(reason):
    scene, _history, service = setup()
    root, parent = container("Building"), container()
    root.children.append(parent)
    scene.groups.append(root)
    action = wall(coordinate_space="parent", parent_id=parent.uid)
    expected = "unavailable_parent"
    if reason == "space":
        action["coordinate_space"] = "model"
        expected = "invalid_coordinate_space"
    elif reason == "locked":
        parent.locked = True
    elif reason == "ancestor":
        root.hidden = True
    else:
        root.component = True
        expected = "invalid_parent"
    assert propose(scene, service, [action])["code"] == expected
    assert not parent.children


def test_component_preview_shares_mesh_and_rejects_classic_children_without_mutation():
    scene, history, service = setup()
    source = container("Assembly")
    source.component = True
    source.xform.translate(4, 0, 0)
    child = Group(AIChangeService._box_mesh(QVector3D(), [1, 1, 1]), "Part")
    source.children.append(child)
    scene.groups.append(source)
    action = dict(action="create_component_instance", name="Copy", source_id=source.uid,
                  offset=[2, 0, 0], coordinate_space="model")
    result = propose(scene, service, [action])
    assert result["code"] == "unsupported_source"
    assert child.xform is None and scene.groups == [source]
    child.xform = QMatrix4x4()
    child.component = False
    result = propose(scene, service, [action])
    assert result["ok"], result
    assert child.xform.isIdentity() and scene.groups == [source]
    assert result["changes"][0]["after"]["bounds"]["min"] == [6, 0, 0]
    service.approve("architecture")
    duplicate = scene.groups[1]
    assert duplicate.mesh is source.mesh
    assert duplicate.children[0].mesh is child.mesh
    assert duplicate.uid != source.uid and duplicate.children[0].uid != child.uid
    assert child.xform.isIdentity()
    assert history.undo() and scene.groups == [source]
    assert history.redo() and scene.groups[1] is duplicate


def test_component_source_must_be_in_task_scope():
    scene, history, _service = setup()
    source, other = container("Source"), container("Other")
    source.component = True
    scene.groups.extend([source, other])
    scene.selection.add(other)
    tasks = AITaskService(scene)
    task = tasks.create("copy component")
    service = AIChangeService(scene, history, tasks)
    result = service.propose(task["task_id"], "", task["base_revision"], "copy-source-001",
        [dict(action="create_component_instance", source_id=source.uid, offset=[1, 0, 0])])
    assert result["code"] == "scope_violation"
    assert len(scene.groups) == 2


def test_wall_component_uses_local_geometry_and_translated_preview():
    scene, _history, service = setup()
    action = wall(component=True)
    action.update(start=[10, 20, 2], end=[10, 26, 2])
    result = propose(scene, service, [action])
    assert result["ok"], result
    bounds = result["changes"][0]["after"]["bounds"]
    assert bounds["min"] == pytest.approx([9.8, 20, 2])
    assert bounds["max"] == pytest.approx([10, 26, 5])
    service.approve("architecture")
    assert scene.groups[0].is_component()
    assert signed_volume(scene.groups[0].mesh) == pytest.approx(3.6)


def test_transforming_creation_parent_cannot_produce_inaccurate_preview():
    scene, history, service = setup()
    parent = container()
    scene.groups.append(parent)
    result = propose(scene, service, [
        dict(action="transform_entities", entity_ids=[parent.uid],
             operation="translate", delta=[10, 0, 0]),
        wall(coordinate_space="parent", parent_id=parent.uid)])
    assert result["code"] == "conflicting_creation_transform"
    assert parent.xform.isIdentity() and not parent.children and not history.undo_stack


@pytest.mark.parametrize("origin", [[1e40, 0, 0], [float("inf"), 0, 0]])
def test_coordinate_overflow_is_rejected(origin):
    scene, _history, service = setup()
    result = propose(scene, service, [dict(action="create_slab", name="Bad",
                                           origin=origin, size=[2, 2, .2])])
    assert not result["ok"] and not scene.groups


def test_slab_collapsing_at_mesh_precision_is_rejected():
    scene, _history, service = setup()
    result = propose(scene, service, [dict(action="create_slab", name="Too thin",
                                           size=[2, 2, 1e-10])])
    assert result["code"] == "invalid_geometry"
    assert not scene.groups
