# SPDX-License-Identifier: GPL-3.0-or-later
"""Validation and aggregation for the versioned AI task corpus."""
from __future__ import annotations

import math
import statistics

CORPUS_SCHEMA = "1.0"
FIXTURE_NAMES = {"empty", "two-boxes-one-selected",
                 "two-boxes-one-selected-active-structure",
                 "mixed-state-model"}
RESULT_FIELDS = {
    "case_id", "provider", "model", "completed", "tokens", "tool_calls",
    "latency_ms", "first_preview_ms", "rollback_ok", "manual_corrections",
}


def validate_corpus(data: dict) -> list[dict]:
    if not isinstance(data, dict) or data.get("schema_version") != CORPUS_SCHEMA:
        raise ValueError(f"corpus schema_version must be {CORPUS_SCHEMA}")
    cases = data.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("corpus cases must be a non-empty array")
    seen = set()
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("each corpus case must be an object")
        required = {"id", "category", "fixture", "intent", "goal",
                    "execution", "expected"}
        missing = required - set(case)
        if missing:
            raise ValueError(f"case is missing {sorted(missing)}")
        case_id = str(case["id"])
        if not case_id or case_id in seen:
            raise ValueError(f"duplicate or empty case id {case_id!r}")
        seen.add(case_id)
        if not isinstance(case["expected"], dict):
            raise ValueError(f"case {case_id} expected must be an object")
        if case["fixture"] not in FIXTURE_NAMES:
            raise ValueError(f"case {case_id} uses unknown fixture")
    return cases


def build_fixture(name: str):
    """Build one small deterministic scene named by the corpus."""
    from core.group import Group
    from core.layers import Layer
    from core.scene import Scene

    if name not in FIXTURE_NAMES:
        raise ValueError(f"unknown AI evaluation fixture {name!r}")
    scene = Scene()
    if name == "empty":
        return scene
    first = Group(name="Box A")
    second = Group(name="Box B")
    scene.groups.extend([first, second])
    if name == "mixed-state-model":
        scene.layers.append(Layer("Locked", locked=True))
        first.hidden = True
        second.layer = "Locked"
        return scene
    scene.select([first])
    if name == "two-boxes-one-selected-active-structure":
        scene.layers.append(Layer("Structure"))
        scene.active_layer = "Structure"
    return scene


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(fraction * len(ordered)) - 1)
    return ordered[index]


def _metric(records: list[dict], key: str) -> dict:
    values = [float(record[key]) for record in records
              if record.get(key) is not None]
    return {"p50": statistics.median(values) if values else None,
            "p95": _percentile(values, 0.95)}


def summarize_results(cases: list[dict], records: list[dict]) -> dict:
    case_ids = {str(case["id"]) for case in cases}
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("each result record must be an object")
        missing = RESULT_FIELDS - set(record)
        if missing:
            raise ValueError(f"result is missing {sorted(missing)}")
        if str(record["case_id"]) not in case_ids:
            raise ValueError(f"unknown case_id {record['case_id']!r}")
        if not str(record["provider"]).strip() or not str(record["model"]).strip():
            raise ValueError("provider and model are required")
        if not isinstance(record["completed"], bool):
            raise ValueError("completed must be boolean")
        if record["rollback_ok"] is not None \
                and not isinstance(record["rollback_ok"], bool):
            raise ValueError("rollback_ok must be boolean or null")
        for key in ("tokens", "tool_calls", "latency_ms", "first_preview_ms",
                    "manual_corrections"):
            value = record[key]
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value) or value < 0):
                raise ValueError(f"{key} must be a finite non-negative number")
    count = len(records)
    completed = sum(bool(record["completed"]) for record in records)
    rollback = [record for record in records
                if record.get("rollback_ok") is not None]
    return {
        "schema_version": CORPUS_SCHEMA,
        "corpus_cases": len(cases),
        "samples": count,
        "completion_rate": completed / count if count else None,
        "rollback_rate": (sum(bool(record["rollback_ok"])
                              for record in rollback) / len(rollback)
                          if rollback else None),
        "manual_corrections": sum(int(record["manual_corrections"])
                                  for record in records),
        "tokens": _metric(records, "tokens"),
        "tool_calls": _metric(records, "tool_calls"),
        "latency_ms": _metric(records, "latency_ms"),
        "first_preview_ms": _metric(records, "first_preview_ms"),
    }
