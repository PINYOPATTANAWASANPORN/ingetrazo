# SPDX-License-Identifier: GPL-3.0-or-later
"""Saved audit files can be checked without an active bridge or model."""
import copy
import hashlib
import json
from types import SimpleNamespace

from core.ai_review_audit import ReviewAuditTrail, verify_bundle
from core.ai_review_export import canonical


def trail():
    result = ReviewAuditTrail()
    task = SimpleNamespace(task_id="task-1", base_revision=4)
    result.record(task, {"task_id": "task-1", "base_revision": 4,
                         "snapshot_id": "snapshot-1", "status": "completed",
                         "summary": "Private project description"})
    result.record(task, {"task_id": "task-1", "base_revision": 4,
                         "snapshot_id": "snapshot-1", "status": "stale"})
    return result


def test_complete_bundle_verifies_independently_and_detects_rewritten_chain():
    bundle = trail().bundle()["bundle"]
    assert verify_bundle(bundle) == {
        "ok": True, "event_count": 2,
        "head_digest": bundle["payload"]["head_digest"], "signed": False}
    assert "Private project description" not in json.dumps(bundle)
    modified = copy.deepcopy(bundle)
    modified["payload"]["events"][0]["status"] = "failed"
    assert not verify_bundle(modified)["ok"]  # outer checksum rejects edits
    modified["integrity"]["payload_digest"] = hashlib.sha256(
        canonical(modified["payload"])).hexdigest()
    assert "event 1" in verify_bundle(modified)["message"]  # chain still rejects
    missing = copy.deepcopy(bundle)
    missing["payload"]["events"].pop(0)
    missing["payload"]["total_events"] = 1
    missing["integrity"]["payload_digest"] = hashlib.sha256(
        canonical(missing["payload"])).hexdigest()
    assert not verify_bundle(missing)["ok"]


def test_rejects_unsupported_format_and_empty_bundle_is_valid():
    assert not verify_bundle({})["ok"]
    assert not verify_bundle({"payload": [], "integrity": {}})["ok"]
    assert verify_bundle(ReviewAuditTrail().bundle()["bundle"])["event_count"] == 0


def test_assistant_saves_history_atomically_and_verifies_file(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication
    from plugins import ai_assistant as plugin
    from views.main_window import MainWindow
    from core.ai_tasks import AITaskService

    app = QApplication.instance() or QApplication([])
    win = MainWindow()
    try:
        panel = plugin.AsistenteDialog(win.viewport, parent=win)
        tasks = panel._task_service()
        task = tasks.create("ตรวจ", execution="analysis_only")
        tasks.record_review(task["task_id"], {
            "task_id": task["task_id"], "base_revision": task["base_revision"],
            "snapshot_id": "snapshot", "status": "failed"})
        destination = tmp_path / "history.json"
        monkeypatch.setattr(plugin.QFileDialog, "getSaveFileName",
                            lambda *args: (str(destination), "JSON"))
        monkeypatch.setattr(plugin.QFileDialog, "getOpenFileName",
                            lambda *args: (str(destination), "JSON"))
        panel._on_export_audit()
        assert destination.exists()
        assert verify_bundle(json.loads(destination.read_text(encoding="utf-8")))["ok"]
        panel._on_verify_audit()
        assert "verified: 1 events" in panel._chat.toPlainText()
        assert len(win.viewport.history.undo_stack) == 0

        # File verification remains independent after the live registry is gone.
        assert AITaskService(win.viewport.scene).review_audit()["total_events"] == 0
        panel._on_verify_audit()
        assert "verified: 1 events" in panel._chat.toPlainText()
    finally:
        win._saved_version = win.viewport.scene.version
        win.close()
