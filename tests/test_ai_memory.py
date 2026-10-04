# SPDX-License-Identifier: GPL-3.0-or-later
"""Explicit project AI memory: validation, persistence, and task snapshots."""
from __future__ import annotations

import pytest

from core.ai_memory import MAX_FACTS, validate_memory
from core.ai_tasks import AITaskService
from core.history import History, SetAIMemoryCommand
from core.scene import Scene
from formats import igz


def test_memory_is_explicit_bounded_and_task_snapshot_does_not_drift():
    assert validate_memory(["  Use metric units  ", "Use metric units", ""]) == [
        "Use metric units"]
    with pytest.raises(ValueError):
        validate_memory([f"fact {i}" for i in range(MAX_FACTS + 1)])

    scene = Scene()
    scene.ai_memory = ["Typical floor height is 3.00 m"]
    tasks = AITaskService(scene)
    task = tasks.create("อธิบายโครงการ", goal="explain")
    scene.ai_memory[0] = "Typical floor height is 4.00 m"

    assert task["project_memory"] == ["Typical floor height is 3.00 m"]
    assert tasks.get(task["task_id"])["project_memory"] == [
        "Typical floor height is 3.00 m"]


def test_memory_edit_is_undoable_and_round_trips_in_igz(tmp_path):
    scene = Scene()
    history = History(scene)
    history.execute(SetAIMemoryCommand([
        "Preferred wall thickness is 0.15 m",
        "Use materials from the local schedule",
    ]))
    assert scene.ai_memory == [
        "Preferred wall thickness is 0.15 m",
        "Use materials from the local schedule",
    ]
    history.undo()
    assert scene.ai_memory == []
    history.redo()

    path = tmp_path / "memory.igz"
    igz.save_scene(scene, path)
    restored = Scene()
    igz.load_into(restored, path)
    assert restored.ai_memory == scene.ai_memory
