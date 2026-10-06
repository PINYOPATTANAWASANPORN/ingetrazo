# SPDX-License-Identifier: GPL-3.0-or-later
"""Human labels must bind to the exact public-fixture review they assess."""
from __future__ import annotations

import copy
import json

import pytest

from core import ai, ai_review
from core.ai_review_assessment import summarize_assessments
from core.ai_review_eval import run_case
from scripts.ai_review_benchmark import main


def _sample(monkeypatch):
    def fake_chat(_provider, _model, _key, _system, messages, **_kwargs):
        packet = json.loads(messages[0]["text"])
        return json.dumps({"summary": "One named group is in scope", "findings": [{
            "entity_id": packet["entities"][0]["id"], "topic": "structure",
            "verdict": "clear", "evidence": "Box A is named"}]})

    monkeypatch.setattr(ai, "chat", fake_chat)
    case = {"id": "selected-object-metadata", "fixture": "two-boxes-one-selected",
            "scope": "selection", "goal": "explain",
            "intent": "Review the selected object's naming and metadata.",
            "expected_scope_count": 1}
    connections = {role: {"provider": "ollama", "model": "test",
                          "key": "", "ollama_url": "local"} for role in ai_review.ROLES}
    record = {"schema_version": "1.0", "run_id": "run-1", **run_case(case, connections)}
    assessment = [{"run_id": "run-1", "case_id": case["id"], "role": role,
                   "review_digest": record["roles"][role]["review_digest"],
                   "assessor": "manual-reviewer", "summary_grounded": "yes",
                   "findings": [{"grounded": "yes", "relevant": "yes"}]}
                  for role in ai_review.ROLES]
    return record, assessment


def test_assessment_counts_judgments_without_inventing_quality_score(monkeypatch):
    record, assessment = _sample(monkeypatch)
    summary = summarize_assessments([record], assessment[:1])
    assert summary["eligible_reviews"] == 2
    assert summary["assessed_reviews"] == 1
    assert summary["unassessed_reviews"] == 1
    assert summary["findings"]["grounded"]["yes"] == 1
    assert summary["quality_score"] is None
    assert "Box A is named" not in json.dumps(record)
    assert "One named group" not in json.dumps(assessment)


@pytest.mark.parametrize("change", [
    lambda a: a[0].update(review_digest="0" * 64),
    lambda a: a[0].update(findings=[]),
    lambda a: a[0]["findings"][0].update(grounded="invented"),
    lambda a: a.append(copy.deepcopy(a[0])),
    lambda a: a[0].update(role="unknown"),
])
def test_assessment_rejects_unbound_or_invalid_judgment(monkeypatch, change):
    record, assessment = _sample(monkeypatch)
    change(assessment)
    with pytest.raises(ValueError):
        summarize_assessments([record], assessment)


def test_cli_rejects_assessments_without_results(capsys):
    with pytest.raises(SystemExit) as failure:
        main(["--assessments", "judgments.json"])
    assert failure.value.code == 2
    assert "--assessments requires --results" in capsys.readouterr().err


def test_cli_limits_prose_display_to_bundled_corpus(tmp_path, capsys):
    custom = tmp_path / "custom.json"
    custom.write_text('{"schema_version":"1.0","cases":[]}', encoding="utf-8")
    with pytest.raises(SystemExit) as failure:
        main(["--run", "--show-findings", "--corpus", str(custom)])
    assert failure.value.code == 2
    assert "bundled public corpus" in capsys.readouterr().err


def test_cli_summarizes_bound_assessments_offline(tmp_path, monkeypatch, capsys):
    record, assessment = _sample(monkeypatch)
    results_path = tmp_path / "results.jsonl"
    results_path.write_text(json.dumps(record) + "\n", encoding="utf-8")
    labels_path = tmp_path / "labels.json"
    labels_path.write_text(json.dumps(assessment), encoding="utf-8")
    assert main(["--results", str(results_path),
                 "--assessments", str(labels_path)]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["human_assessment"]["assessed_reviews"] == 2
    assert output["human_assessment"]["findings"]["grounded"]["yes"] == 2
    assert output["quality_score"] is None
