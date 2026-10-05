# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json

import pytest
from core.ai_review import ROLES, snapshot, combine_reports
from core.ai_review_export import canonical
from core.ai_tasks import AITaskService
from core.scene import Scene


def completed(scene, tasks, failures=0):
    task = tasks.create("ตรวจโมเดล", execution="analysis_only")
    packet = snapshot(scene, task)
    results = []
    for i, role in enumerate(ROLES):
        entry = dict(role=role, ok=i >= failures, provider="fake", model="test",
                     api_key="SECRET", submission_token="SECRET")
        entry.update(dict(error="Unavailable") if i < failures else
                     dict(summary="ตรวจแล้ว", findings=[]))
        results.append(entry)
    report = combine_reports(packet, results)
    report["raw_snapshot"] = "SECRET"
    tasks.record_review(task["task_id"], report)
    return task["task_id"]


@pytest.mark.parametrize("failures,status", [(0, "completed"), (1, "partial"), (2, "failed")])
def test_export_integrity_allowlist_and_status(failures, status):
    scene = Scene()
    tasks = AITaskService(scene)
    task_id = completed(scene, tasks, failures)
    result = tasks.export_review(task_id)
    assert result["ok"]
    bundle = result["bundle"]
    assert bundle["payload"]["report"]["status"] == status
    assert bundle["integrity"]["payload_digest"] == hashlib.sha256(canonical(bundle["payload"])).hexdigest()
    assert bundle["integrity"]["signed"] is False
    assert "SECRET" not in json.dumps(bundle)
    scene.version += 1
    assert not tasks.export_review(task_id)["ok"]


def test_unfinished_or_unknown_task_not_exportable():
    tasks = AITaskService(Scene())
    task = tasks.create("check", execution="analysis_only")
    assert not tasks.export_review(task["task_id"])["ok"]
    assert not tasks.export_review("missing")["ok"]


@pytest.mark.parametrize("change", [False, True])
def test_assistant_atomic_export_and_modal_revision_check(tmp_path, monkeypatch, change):
    from PySide6.QtWidgets import QApplication
    from plugins import ai_assistant as plugin
    from views.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    win = MainWindow()
    try:
        panel = plugin.AsistenteDialog(win.viewport, parent=win)
        panel._active_task_id = completed(win.viewport.scene, panel._task_service())
        destination = tmp_path / "review.json"
        def choose(*args):
            if change:
                win.viewport.scene.version += 1
            return str(destination), "JSON"
        monkeypatch.setattr(plugin.QFileDialog, "getSaveFileName", choose)
        panel._on_export_review()
        assert destination.exists() is not change
        if not change:
            bundle = json.loads(destination.read_text(encoding="utf-8"))
            assert bundle["payload"]["report"]["specialists"][0]["summary"] == "ตรวจแล้ว"
        assert len(win.viewport.history.undo_stack) == 0
    finally:
        win._saved_version = win.viewport.scene.version
        win.close()
