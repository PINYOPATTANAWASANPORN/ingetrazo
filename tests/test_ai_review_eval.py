# SPDX-License-Identifier: GPL-3.0-or-later
"""The benchmark must measure the real review contract without saving prose."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from core import ai, ai_review
from core.ai_review_eval import (make_snapshot, run_case,
                                 summarize_review_records, validate_review_corpus)
from scripts.ai_review_benchmark import load_connections, main

ROOT = Path(__file__).parents[1]
CORPUS = ROOT / "benchmarks/ai/review-corpus-v1.json"


def cases():
    return validate_review_corpus(json.loads(CORPUS.read_text(encoding="utf-8")))


def test_review_corpus_builds_real_read_only_snapshots(capsys):
    found = cases()
    assert len(found) == 3
    for case in found:
        packet = make_snapshot(case)
        assert packet["scope_kind"] == case["scope"]
        assert len(packet["entities"]) == case["expected_scope_count"]
        assert packet == make_snapshot(case)
    assert main(["--corpus", str(CORPUS)]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["provider_calls"] == 0
    assert len(summary["cases"]) == 3


def test_review_benchmark_records_metadata_without_secret_or_prose(monkeypatch):
    case = cases()[0]
    secret = "example-secret-never-save"

    def fake_chat(_provider, _model, _key, _system, messages, **_kwargs):
        packet = json.loads(messages[0]["text"])
        return json.dumps({"summary": "private review prose", "findings": [{
            "entity_id": packet["entities"][0]["id"], "topic": "material",
            "verdict": "concern", "evidence": "private evidence text"}]})

    monkeypatch.setattr(ai, "chat", fake_chat)
    connections = {role: {"provider": "openai", "model": "test-model",
                          "key": secret, "ollama_url": ""}
                   for role in ai_review.ROLES}
    record = run_case(case, connections)
    encoded = json.dumps(record)
    assert record["status"] == "completed"
    assert record["document_changed"] is False
    assert record["tokens"] is None and record["quality_score"] is None
    assert record["input_bytes"] > 0 and record["latency_ms"] >= 0
    assert all(role["latency_ms"] >= 0 and role["finding_count"] == 1
               for role in record["roles"].values())
    assert all(role["failure_code"] is None for role in record["roles"].values())
    assert all(text not in encoded for text in
               (secret, "private review prose", "private evidence text"))
    summary = summarize_review_records(cases(), [
        {"schema_version": "1.0", **record}])
    assert summary["completion_rate"] == 1
    assert summary["latency_ms"]["p50"] == record["latency_ms"]
    assert len(summary["by_role"]) == 2
    assert summary["tokens"] is None and summary["quality_score"] is None

    fabricated = {"schema_version": "1.0", **record, "tokens": 100}
    with pytest.raises(ValueError, match="unsupported"):
        summarize_review_records(cases(), [fabricated])


def test_connection_config_rejects_literal_keys_and_never_echoes_secret(tmp_path,
                                                                          monkeypatch):
    config = {"schema_version": "1.0", "roles": {
        role: {"provider": "openai", "model": "fixed-model",
               "key_env": "REVIEW_TEST_KEY"} for role in ai_review.ROLES}}
    path = tmp_path / "providers.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    monkeypatch.setenv("REVIEW_TEST_KEY", "private-test-key")
    resolved = load_connections(path)
    assert all(item["key"] == "private-test-key" for item in resolved.values())
    config["roles"]["model_structure"]["key"] = "private-test-key"
    path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported fields") as failure:
        load_connections(path)
    assert "private-test-key" not in str(failure.value)


def test_runner_writes_only_metadata_and_summarizes_offline(tmp_path, monkeypatch,
                                                              capsys):
    def fake_chat(_provider, _model, _key, _system, _messages, **_kwargs):
        return json.dumps({"summary": "sensitive summary", "findings": []})

    monkeypatch.setattr(ai, "chat", fake_chat)
    config = {"schema_version": "1.0", "roles": {
        role: {"provider": "ollama", "model": "test-model"}
        for role in ai_review.ROLES}}
    config_path = tmp_path / "providers.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    output = tmp_path / "run.jsonl"
    assert main(["--run", "--config", str(config_path),
                 "--output", str(output)]) == 0
    assert "sensitive summary" not in output.read_text(encoding="utf-8")
    records = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert len(records) == len(cases())
    assert {r["application_commit"] for r in records}
    assert all(r["tokens"] is None and r["quality_score"] is None for r in records)
    capsys.readouterr()
    assert main(["--results", str(output)]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["samples"] == len(cases())
    assert summary["completion_rate"] == 1
    with pytest.raises(FileExistsError):
        main(["--run", "--config", str(config_path),
              "--output", str(output)])


def test_invalid_corpus_and_failed_role_latency(monkeypatch):
    data = json.loads(CORPUS.read_text(encoding="utf-8"))
    data["cases"].append(dict(data["cases"][0]))
    with pytest.raises(ValueError, match="duplicated"):
        validate_review_corpus(data)

    def failing_chat(*_args, **_kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(ai, "chat", failing_chat)
    packet = make_snapshot(cases()[0])
    report = ai_review.run_review(packet, "ollama", "test", "", "local",
                                  ai_review.ReviewCancellation())
    assert report["status"] == "failed"
    assert all(isinstance(role["latency_ms"], int) and role["latency_ms"] >= 0
               for role in report["specialists"])


def test_failure_summary_counts_only_safe_codes_and_reads_older_records(monkeypatch):
    monkeypatch.setattr(ai, "chat", lambda *_args, **_kwargs: "not JSON")
    record = run_case(cases()[0], {role: {
        "provider": "ollama", "model": "test", "key": "", "ollama_url": "local"}
        for role in ai_review.ROLES})
    assert {item["failure_code"] for item in record["roles"].values()} == {"invalid_json"}
    summary = summarize_review_records(cases(), [{"schema_version": "1.0", **record}])
    assert all(item["failures"] == {"invalid_json": 1} for item in summary["by_role"])
    assert "not JSON" not in json.dumps(record)

    legacy = json.loads(json.dumps(record))
    for outcome in legacy["roles"].values():
        del outcome["failure_code"]
    summary = summarize_review_records(cases(), [{"schema_version": "1.0", **legacy}])
    assert all(item["failures"] == {"unclassified": 1} for item in summary["by_role"])

    invalid = json.loads(json.dumps(record))
    invalid["roles"]["model_structure"]["failure_code"] = "private provider response"
    with pytest.raises(ValueError, match="failure code"):
        summarize_review_records(cases(), [{"schema_version": "1.0", **invalid}])
