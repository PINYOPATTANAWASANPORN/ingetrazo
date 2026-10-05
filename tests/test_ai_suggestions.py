# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.ai_eval import build_fixture, summarize_results, validate_corpus
from core.ai_suggestions import suggestions
from core.group import Group
from core.layers import Layer
from core.scene import Scene


def test_suggestions_follow_empty_model_and_stable_selection():
    scene = Scene()
    empty = suggestions(scene)
    assert [item["goal"] for item in empty] == ["create", "create", "explain"]
    assert all(item["scope"] == "visible_model" for item in empty)

    chair = Group(name="Chair")
    table = Group(name="Table")
    scene.groups.extend([chair, table])
    scene.layers.append(Layer("Structure"))
    scene.active_layer = "Structure"
    scene.select([chair])
    selected = suggestions(scene)
    assert [item["label"] for item in selected] == [
        "Describe selection", "Hide selection", "Lock selection",
        "Assign active tag"]
    assert all(item["scope"] == "selection" for item in selected)
    assert selected[0]["execution"] == "analysis_only"
    assert selected[-1]["goal"] == "revise"

    # Face/edge selections cannot be represented by stable task entity IDs,
    # so they must not produce a selection-scoped chip.
    scene.selection = {object()}
    scene.bump_view()
    assert suggestions(scene)[0]["scope"] == "visible_model"


def test_versioned_ai_corpus_and_metric_aggregation():
    path = Path(__file__).parents[1] / "benchmarks/ai/task-corpus-v1.json"
    cases = validate_corpus(json.loads(path.read_text(encoding="utf-8")))
    assert len(cases) == 8
    fixtures = {case["fixture"]: build_fixture(case["fixture"])
                for case in cases}
    assert not fixtures["empty"].groups
    assert len(fixtures["mixed-state-model"].groups) == 2
    assert len(fixtures["two-boxes-one-selected"].selection) == 1
    records = [
        {"case_id": cases[0]["id"], "provider": "local", "model": "test",
         "completed": True, "tokens": 100, "tool_calls": 1,
         "latency_ms": 1000, "first_preview_ms": 400,
         "rollback_ok": True, "manual_corrections": 0},
        {"case_id": cases[1]["id"], "provider": "local", "model": "test",
         "completed": False, "tokens": 200, "tool_calls": 3,
         "latency_ms": 2000, "first_preview_ms": 800,
         "rollback_ok": False, "manual_corrections": 2},
    ]
    summary = summarize_results(cases, records)
    assert summary["completion_rate"] == 0.5
    assert summary["rollback_rate"] == 0.5
    assert summary["manual_corrections"] == 2
    assert summary["tokens"] == {"p50": 150.0, "p95": 200.0}
    assert summary["first_preview_ms"]["p50"] == 600.0

    broken = dict(records[0], tokens=-1)
    with pytest.raises(ValueError, match="tokens"):
        summarize_results(cases, [broken])
