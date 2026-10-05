# SPDX-License-Identifier: GPL-3.0-or-later
import json
import threading

import pytest
from core import ai, ai_review
from core.ai_tasks import AITaskService
from core.group import Group
from core.scene import Scene


def model():
    scene = Scene()
    group = Group(name="Chair")
    scene.groups.append(group)
    tasks = AITaskService(scene)
    task = tasks.create("check the chair", execution="analysis_only")
    return scene, group, tasks, task


def reply(uid, verdict="concern"):
    return json.dumps(dict(summary="Review of supplied metadata", findings=[
        dict(entity_id=uid, topic="material", verdict=verdict,
             evidence="The supplied material name is empty.")]))


def test_parallel_specialists_share_snapshot_and_preserve_conflicts(monkeypatch):
    scene, group, _tasks, task = model()
    packet = ai_review.snapshot(scene, task)
    barrier = threading.Barrier(2)
    seen = []
    def chat(provider, model, key, system, messages, **kwargs):
        barrier.wait(timeout=3)  # proves both requests run concurrently
        seen.append(messages[0]["text"])
        verdict = "concern" if "organisation" in system else "clear"
        return reply(group.uid, verdict)
    monkeypatch.setattr(ai, "chat", chat)
    report = ai_review.run_review(packet, "local", "test", "", "localhost",
                                  ai_review.ReviewCancellation())
    assert report["status"] == "completed" and report["changed"] is False
    assert len(seen) == 2 and seen[0] == seen[1]
    assert len(report["conflicts"]) == 1
    assert scene.content_version == task["base_revision"] and group.name == "Chair"
    assert "CONFLICT (unresolved)" in ai_review.report_text(report)


@pytest.mark.parametrize("bad", [
    '{"actions":[{"action":"rename_entities"}]}',
    '```python\nprint("never executed")\n```',
    reply("outside-scope"),
    'x' * (ai_review.MAX_REPLY_CHARS + 1),
])
def test_malformed_or_write_responses_fail_without_model_changes(monkeypatch, bad):
    scene, group, _tasks, task = model()
    monkeypatch.setattr(ai, "chat", lambda *a, **k: bad)
    report = ai_review.run_review(ai_review.snapshot(scene, task), "local", "m", "", "url",
                                  ai_review.ReviewCancellation())
    assert report["status"] == "failed"
    assert all(not item["ok"] for item in report["specialists"])
    assert group.name == "Chair" and scene.content_version == task["base_revision"]


@pytest.mark.parametrize("bad, code", [
    ("not JSON", "invalid_json"),
    ('{"summary":"ok","findings":[],"actions":[]}', "invalid_schema"),
    (reply("outside-scope"), "out_of_scope_entity"),
    ("x" * (ai_review.MAX_REPLY_CHARS + 1), "response_too_large"),
])
def test_failed_review_has_bounded_diagnostic_code(monkeypatch, bad, code):
    scene, _group, _tasks, task = model()
    monkeypatch.setattr(ai, "chat", lambda *a, **k: bad)
    report = ai_review.run_review(ai_review.snapshot(scene, task), "ollama", "m", "", "url",
                                  ai_review.ReviewCancellation())
    assert {item["failure_code"] for item in report["specialists"]} == {code}


def test_provider_failure_code_does_not_contain_provider_message(monkeypatch):
    scene, _group, _tasks, task = model()
    monkeypatch.setattr(ai, "chat", lambda *a, **k: (_ for _ in ()).throw(
        RuntimeError("private provider response")))
    report = ai_review.run_review(ai_review.snapshot(scene, task), "ollama", "m", "", "url",
                                  ai_review.ReviewCancellation())
    assert {item["failure_code"] for item in report["specialists"]} == {"provider_error"}


def test_empty_snapshot_prompt_disallows_invented_entity_findings(monkeypatch):
    scene = Scene()
    task = AITaskService(scene).create("explain empty model", execution="analysis_only")
    systems = []
    def chat(_provider, _model, _key, system, _messages, **_kwargs):
        systems.append(system)
        return '{"summary":"No model entities were supplied.","findings":[]}'
    monkeypatch.setattr(ai, "chat", chat)
    report = ai_review.run_review(ai_review.snapshot(scene, task), "ollama", "m", "", "url",
                                  ai_review.ReviewCancellation())
    assert report["status"] == "completed"
    assert all("If that array is empty, return findings: []" in system
               for system in systems)


def test_one_provider_failure_retains_other_review_as_partial(monkeypatch):
    scene, group, _tasks, task = model()
    def chat(_p, _m, _k, system, *_args, **_kwargs):
        if "organisation" in system:
            raise RuntimeError("provider unavailable")
        return reply(group.uid)
    monkeypatch.setattr(ai, "chat", chat)
    report = ai_review.run_review(ai_review.snapshot(scene, task), "local", "m", "", "url",
                                  ai_review.ReviewCancellation())
    assert report["status"] == "partial"
    assert sum(item["ok"] for item in report["specialists"]) == 1


def test_snapshot_is_detached_scoped_and_revision_pinned():
    scene, group, tasks, _task = model()
    outside = Group(name="Outside")
    scene.groups.append(outside)
    scene.selection.add(group)
    task = tasks.create("inspect selected", execution="analysis_only")
    packet = ai_review.snapshot(scene, task)
    assert [e["id"] for e in packet["entities"]] == [group.uid]
    group.name = "Later"
    assert packet["entities"][0]["name"] == "Chair"
    scene.version += 1
    with pytest.raises(ValueError, match="stale"):
        ai_review.snapshot(scene, task)


def test_snapshot_rejects_truncation_and_write_mode():
    scene, _group, tasks, task = model()
    task["scope"]["truncated"] = True
    with pytest.raises(ValueError, match="200"):
        ai_review.snapshot(scene, task)
    task = tasks.create("create box")
    with pytest.raises(ValueError, match="analysis-only"):
        ai_review.snapshot(scene, task)


def test_cancel_closes_both_active_requests_and_no_result_is_returned(monkeypatch):
    scene, _group, _tasks, task = model()
    cancel = ai_review.ReviewCancellation()
    barrier = threading.Barrier(3)
    closed = []
    class Response:
        def close(self):
            closed.append(self)
    def chat(*args, cancel_token, **kwargs):
        response = Response()
        cancel_token.bind_response(response)
        barrier.wait(timeout=3)
        cancel_token.wait(3)
        raise ai.CancelledError("cancelled")
    monkeypatch.setattr(ai, "chat", chat)
    outcomes = []
    def worker():
        try:
            ai_review.run_review(ai_review.snapshot(scene, task), "local", "m", "", "url", cancel)
        except ai.CancelledError:
            outcomes.append("cancelled")
    thread = threading.Thread(target=worker)
    thread.start()
    barrier.wait(timeout=3)
    cancel.cancel()
    thread.join(timeout=4)
    assert not thread.is_alive() and outcomes == ["cancelled"]
    assert len(closed) == 2


def test_specialists_use_separate_models_and_report_requested_identity(monkeypatch):
    scene, group, _tasks, task = model()
    calls = []
    choices = {"model_structure": "structure-model", "task_requirements": "requirements-model"}
    def chat(provider, selected_model, key, *args, **kwargs):
        calls.append((provider, selected_model, key))
        return reply(group.uid)
    monkeypatch.setattr(ai, "chat", chat)
    report = ai_review.run_review(ai_review.snapshot(scene, task), "local", "main-model",
        "private-key", "url", ai_review.ReviewCancellation(), choices)
    assert {item[1] for item in calls} == set(choices.values())
    assert all(item[0] == "local" and item[2] == "private-key" for item in calls)
    assert {r["role"]: r["model"] for r in report["specialists"]} == choices
    assert "private-key" not in json.dumps(report)
    assert "structure-model" in ai_review.report_text(report)


def test_empty_role_model_inherits_main_and_failure_keeps_model_name(monkeypatch):
    scene, _group, _tasks, task = model()
    calls = []
    def chat(provider, selected_model, *args, **kwargs):
        calls.append(selected_model)
        raise ValueError("model unavailable")
    monkeypatch.setattr(ai, "chat", chat)
    report = ai_review.run_review(ai_review.snapshot(scene, task), "local", "main-model",
        "", "url", ai_review.ReviewCancellation(), {"model_structure": "  "})
    assert calls == ["main-model", "main-model"]
    assert report["status"] == "failed"
    assert all(r["model"] == "main-model" for r in report["specialists"])


@pytest.mark.parametrize("choices", [{"unknown": "x"}, {"model_structure": 3},
                                     {"model_structure": "x" * 201}])
def test_invalid_model_overrides_fail_before_provider_call(monkeypatch, choices):
    scene, _group, _tasks, task = model()
    def unexpected(*args, **kwargs):
        pytest.fail("invalid model choices must not call a provider")
    monkeypatch.setattr(ai, "chat", unexpected)
    with pytest.raises(ValueError):
        ai_review.run_review(ai_review.snapshot(scene, task), "local", "m", "", "url",
                             ai_review.ReviewCancellation(), choices)


def test_each_role_uses_its_own_provider_and_key_without_leaking_secrets(monkeypatch):
    scene, _group, _tasks, task = model()
    packet = ai_review.snapshot(scene, task)
    calls = []
    def chat(provider, selected_model, key, _system, messages, **kwargs):
        calls.append((provider, selected_model, key, messages[0]["text"]))
        if provider == "gemini":
            raise RuntimeError("request failed with " + key)
        return json.dumps({"summary": "checked", "findings": []})
    monkeypatch.setattr(ai, "chat", chat)
    connections = {
        "model_structure": {"provider": "anthropic", "model": "structure", "key": "sk-ant-secret",
                            "ollama_url": ""},
        "task_requirements": {"provider": "gemini", "model": "requirements", "key": "AIza-secret",
                              "ollama_url": ""},
    }
    report = ai_review.run_review(packet, "ollama", "unused", "", "localhost",
                                  ai_review.ReviewCancellation(), role_connections=connections)
    assert report["status"] == "partial"
    assert {(p, m, k) for p, m, k, _ in calls} == {
        ("anthropic", "structure", "sk-ant-secret"),
        ("gemini", "requirements", "AIza-secret")}
    assert calls[0][3] == calls[1][3]
    assert "sk-ant-secret" not in json.dumps(report)
    assert "AIza-secret" not in json.dumps(report)
    assert "[redacted]" in json.dumps(report)


@pytest.mark.parametrize("connections", [
    {},
    {"model_structure": {}, "task_requirements": {}},
    {"model_structure": {"provider": "openai", "model": "x", "key": "", "ollama_url": ""},
     "task_requirements": {"provider": "ollama", "model": "x", "key": "", "ollama_url": ""}},
])
def test_bad_role_connections_fail_before_any_provider_request(monkeypatch, connections):
    _scene, _group, _tasks, task = model()
    monkeypatch.setattr(ai, "chat", lambda *args, **kwargs:
                        pytest.fail("invalid connections must not dispatch"))
    with pytest.raises(ValueError):
        ai_review.run_review(ai_review.snapshot(_scene, task), "ollama", "m", "", "url",
                             ai_review.ReviewCancellation(), role_connections=connections)
