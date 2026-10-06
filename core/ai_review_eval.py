# SPDX-License-Identifier: GPL-3.0-or-later
"""Metadata-only benchmark records for the existing read-only review path.

This module deliberately does not score reviewer prose. A valid JSON response
is not evidence that a provider found the right issue; that needs human review.
"""
from __future__ import annotations

import json
import math
import statistics
import time

from core import ai_review
from core.ai_eval import FIXTURE_NAMES, build_fixture
from core.ai_tasks import AITaskService

SCHEMA_VERSION = "1.0"
CASE_FIELDS = {"id", "fixture", "scope", "goal", "intent", "expected_scope_count"}
SCOPES = {"selection", "visible_model", "whole_model"}
GOALS = {"check", "explain"}
RESPONSE_MODES = {"schema", "prompt", "prompt_fallback", "unspecified"}


def validate_review_corpus(data: dict) -> list[dict]:
    if not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("review corpus schema_version must be 1.0")
    cases = data.get("cases")
    if not isinstance(cases, list) or not 1 <= len(cases) <= 32:
        raise ValueError("review corpus needs 1-32 cases")
    seen = set()
    for case in cases:
        if not isinstance(case, dict) or set(case) != CASE_FIELDS:
            raise ValueError("review case fields do not match the schema")
        case_id = case["id"]
        if (not isinstance(case_id, str) or not 1 <= len(case_id) <= 64
                or not all(ch.isascii() and (ch.islower() or ch.isdigit() or ch == "-")
                           for ch in case_id) or case_id in seen):
            raise ValueError("review case ID is invalid or duplicated")
        seen.add(case_id)
        if (not isinstance(case["fixture"], str) or
                not isinstance(case["scope"], str) or
                case["fixture"] not in FIXTURE_NAMES or case["scope"] not in SCOPES):
            raise ValueError(f"unknown review fixture or scope: {case_id}")
        if not isinstance(case["goal"], str) or case["goal"] not in GOALS:
            raise ValueError(f"review goal must be read-only: {case_id}")
        if not isinstance(case["intent"], str) or not 1 <= len(case["intent"].strip()) <= 1000:
            raise ValueError(f"invalid review intent: {case_id}")
        count = case["expected_scope_count"]
        if isinstance(count, bool) or not isinstance(count, int) or not 0 <= count <= 200:
            raise ValueError(f"invalid expected scope count: {case_id}")
    return cases


def make_snapshot(case: dict) -> dict:
    """Use the same task and snapshot contracts as the Assistant."""
    scene = build_fixture(case["fixture"])
    # Group and task IDs are normally random. Fix them in this public fixture
    # so every provider receives byte-identical metadata across runs.
    for index, group in enumerate(scene.groups, 1):
        group.uid = f"benchmark-{index:04d}"
    task = AITaskService(scene).create(case["intent"], scope=case["scope"],
                                        goal=case["goal"], execution="analysis_only")
    if not task.get("ok"):
        raise ValueError(f"review fixture task failed: {case['id']}")
    task["task_id"] = "benchmark-" + case["id"]
    packet = ai_review.snapshot(scene, task)
    if len(packet["entities"]) != case["expected_scope_count"]:
        raise ValueError(f"review fixture scope drifted: {case['id']}")
    return packet


def run_case(case: dict, connections: dict) -> dict:
    """Run both specialists and return only bounded measurement metadata."""
    packet = make_snapshot(case)
    input_bytes = len(json.dumps(packet, ensure_ascii=False,
                                 separators=(",", ":")).encode("utf-8"))
    started = time.perf_counter()
    first = connections["model_structure"]
    report = ai_review.run_review(
        packet, first["provider"], first["model"], first["key"],
        first["ollama_url"], ai_review.ReviewCancellation(),
        role_connections=connections)
    latency_ms = round((time.perf_counter() - started) * 1000)
    roles = {}
    for result in report["specialists"]:
        role = result["role"]
        role_ms = result.get("latency_ms")
        if (isinstance(role_ms, bool) or not isinstance(role_ms, (int, float))
                or not math.isfinite(role_ms) or role_ms < 0):
            raise ValueError("specialist latency measurement is missing")
        roles[role] = {
            "provider": result["provider"], "model": result["model"],
            "response_mode": result.get("response_mode", "unspecified"),
            "ok": result["ok"], "latency_ms": role_ms,
            "finding_count": len(result.get("findings", [])),
            "failure_code": result.get("failure_code") if not result["ok"] else None,
            "usage": result.get("usage"),
        }
    totals = [item["usage"].get("total_tokens") if isinstance(item["usage"], dict)
              else None for item in roles.values()]
    return {
        "case_id": case["id"], "status": report["status"],
        "input_bytes": input_bytes, "latency_ms": latency_ms,
        "roles": roles, "conflict_count": len(report["conflicts"]),
        "document_changed": bool(report["changed"]),
        "tokens": sum(totals) if all(total is not None for total in totals) else None,
        "quality_score": None,
    }


def summarize_review_records(cases: list[dict], records: list[dict]) -> dict:
    """Aggregate only measured values; unknown tokens and quality stay null."""
    known = {case["id"] for case in cases}
    groups: dict[tuple[str, str, str, str], list[dict]] = {}
    for record in records:
        if (not isinstance(record, dict) or
                record.get("schema_version") != SCHEMA_VERSION or
                not isinstance(record.get("case_id"), str) or
                record["case_id"] not in known or
                not isinstance(record.get("status"), str) or
                record["status"] not in {"completed", "partial", "failed"} or
                record.get("quality_score") is not None):
            raise ValueError("invalid or unsupported review benchmark record")
        _number(record.get("latency_ms"))
        _tokens(record.get("tokens"))
        roles = record.get("roles")
        if not isinstance(roles, dict) or set(roles) != set(ai_review.ROLES):
            raise ValueError("review record must contain both role outcomes")
        for role, outcome in roles.items():
            if not isinstance(outcome, dict):
                raise ValueError("invalid role outcome")
            provider, model = outcome.get("provider"), outcome.get("model")
            if (not isinstance(provider, str) or not provider or
                    not isinstance(model, str) or not model or
                    not isinstance(outcome.get("ok"), bool)):
                raise ValueError("invalid role identity or status")
            response_mode = outcome.get("response_mode", "unspecified")
            if not isinstance(response_mode, str) or response_mode not in RESPONSE_MODES:
                raise ValueError("invalid specialist response mode")
            failure_code = outcome.get("failure_code")
            if (outcome["ok"] and failure_code is not None) or (
                    not outcome["ok"] and failure_code is not None and
                    failure_code not in ai_review.FAILURE_CODES):
                raise ValueError("invalid specialist failure code")
            usage = outcome.get("usage")
            if usage is not None:
                if not isinstance(usage, dict) or set(usage) != {
                        "input_tokens", "output_tokens", "total_tokens"}:
                    raise ValueError("invalid specialist usage")
                for value in usage.values():
                    _tokens(value)
                if all(value is None for value in usage.values()):
                    raise ValueError("empty specialist usage")
            _number(outcome.get("latency_ms"))
            groups.setdefault((role, provider, model, response_mode), []).append(outcome)
        totals = [outcome.get("usage", {}).get("total_tokens")
                  if isinstance(outcome.get("usage"), dict) else None
                  for outcome in roles.values()]
        if record.get("tokens") != (sum(totals) if all(
                total is not None for total in totals) else None):
            raise ValueError("review record token total does not match reported usage")
    by_role = []
    for (role, provider, model, response_mode), outcomes in sorted(groups.items()):
        by_role.append({
            "role": role, "provider": provider, "model": model,
            "response_mode": response_mode,
            "samples": len(outcomes),
            "ok_rate": sum(item["ok"] for item in outcomes) / len(outcomes),
            "latency_ms": _latencies([item["latency_ms"] for item in outcomes]),
            "tokens": _token_summary([
                item["usage"]["total_tokens"] for item in outcomes
                if isinstance(item.get("usage"), dict) and
                item["usage"]["total_tokens"] is not None]),
            "failures": {code: sum(not item["ok"] and
                                   (item.get("failure_code") or "unclassified") == code
                                   for item in outcomes)
                         for code in sorted(ai_review.FAILURE_CODES | {"unclassified"})
                         if any(not item["ok"] and
                                (item.get("failure_code") or "unclassified") == code
                                for item in outcomes)},
        })
    return {
        "schema_version": SCHEMA_VERSION,
        "corpus_cases": len(cases), "samples": len(records),
        "completion_rate": (sum(r["status"] == "completed" for r in records)
                            / len(records) if records else None),
        "latency_ms": _latencies([r["latency_ms"] for r in records]),
        "by_role": by_role,
        "tokens": _token_summary([r["tokens"] for r in records
                                  if r.get("tokens") is not None]),
        "quality_score": None,
    }


def _tokens(value) -> None:
    if value is not None and (isinstance(value, bool) or
                              not isinstance(value, int) or
                              not 0 <= value <= 1_000_000_000):
        raise ValueError("tokens must be a reported non-negative integer or null")


def _token_summary(values: list[int]) -> dict | None:
    return {"samples": len(values), **_latencies(values)} if values else None


def _number(value) -> None:
    if (isinstance(value, bool) or not isinstance(value, (int, float)) or
            not math.isfinite(value) or value < 0):
        raise ValueError("latency must be a finite non-negative number")


def _latencies(values: list[int | float]) -> dict:
    if not values:
        return {"p50": None, "p95": None}
    ordered = sorted(values)
    return {"p50": statistics.median(ordered),
            "p95": ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]}
