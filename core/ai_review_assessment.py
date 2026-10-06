# SPDX-License-Identifier: GPL-3.0-or-later
"""Validate human judgments bound to public-fixture specialist responses.

These labels measure assessed grounding and relevance, not completeness or an
overall quality score. The assessment file stores no reviewer prose.
"""
from __future__ import annotations

import re

from core import ai_review
from core.ai_review_eval import make_snapshot

LABELS = {"yes", "no", "unclear"}
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
ASSESSMENT_FIELDS = {"run_id", "case_id", "role", "review_digest", "assessor",
                     "summary_grounded", "findings"}
CHECK_FIELDS = {"case_id", "id", "entity_id", "field", "equals", "roles"}
FACT_FIELDS = {"name", "layer", "hidden", "locked", "visible",
               "layer_visible", "layer_locked", "parent_id", "child_count"}


def validate_coverage_reference(data: dict, cases: list[dict]) -> dict:
    """Accept only checkable facts from the versioned public snapshots."""
    if (not isinstance(data, dict) or set(data) != {
            "schema_version", "description", "checks"} or
            data["schema_version"] != "1.0" or
            not isinstance(data["description"], str) or
            not isinstance(data["checks"], list) or
            not 1 <= len(data["checks"]) <= 100):
        raise ValueError("coverage reference schema is invalid")
    snapshots = {case["id"]: make_snapshot(case) for case in cases}
    by_role = {(case_id, role): [] for case_id in snapshots for role in ai_review.ROLES}
    seen = set()
    for check in data["checks"]:
        if not isinstance(check, dict) or set(check) != CHECK_FIELDS:
            raise ValueError("coverage check fields are invalid")
        case_id, check_id = check["case_id"], check["id"]
        if (not isinstance(case_id, str) or case_id not in snapshots or
                not isinstance(check_id, str) or not re.fullmatch(
                    r"[a-z0-9][a-z0-9-]{0,63}", check_id) or
                (case_id, check_id) in seen):
            raise ValueError("coverage check identity is invalid or duplicated")
        seen.add((case_id, check_id))
        roles = check["roles"]
        if (not isinstance(roles, list) or not roles or
                len(roles) != len(set(role for role in roles if isinstance(role, str)))
                or any(not isinstance(role, str) or role not in ai_review.ROLES
                       for role in roles)):
            raise ValueError("coverage check roles are invalid")
        packet = snapshots[case_id]
        field, entity_id = check["field"], check["entity_id"]
        if field == "entity_count" and entity_id is None:
            actual = len(packet["entities"])
        elif isinstance(field, str) and field in FACT_FIELDS and isinstance(entity_id, str):
            entity = next((item for item in packet["entities"]
                           if item["id"] == entity_id), None)
            if entity is None:
                raise ValueError("coverage check refers to an absent entity")
            actual = entity[field]
        else:
            raise ValueError("coverage check field or entity is invalid")
        if type(check["equals"]) is not type(actual) or check["equals"] != actual:
            raise ValueError("coverage reference disagrees with the public snapshot")
        for role in roles:
            by_role[(case_id, role)].append(check_id)
    return by_role


def summarize_assessments(records: list[dict], assessments: list[dict],
                          coverage_reference: dict | None = None) -> dict:
    """Check provenance, one judgment per finding, and assessment coverage."""
    eligible = {}
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("run_id"), str):
            raise ValueError("review records need a run_id")
        roles = record.get("roles")
        if not isinstance(roles, dict) or set(roles) != set(ai_review.ROLES):
            raise ValueError("review record roles are invalid")
        for role, outcome in roles.items():
            if not isinstance(outcome, dict) or not isinstance(outcome.get("ok"), bool):
                raise ValueError("review role outcome is invalid")
            if not outcome["ok"]:
                continue
            digest = outcome.get("review_digest")
            count = outcome.get("finding_count")
            if (not isinstance(digest, str) or not DIGEST.fullmatch(digest)
                    or isinstance(count, bool) or not isinstance(count, int)
                    or not 0 <= count <= 20):
                raise ValueError("successful review lacks a valid digest or finding count")
            key = (record["run_id"], record.get("case_id"), role)
            if key in eligible:
                raise ValueError("duplicate review outcome")
            eligible[key] = (digest, count)

    seen = set()
    finding_labels = {dimension: {label: 0 for label in LABELS}
                      for dimension in ("grounded", "relevant")}
    summary_labels = {label: 0 for label in LABELS}
    coverage_labels = {label: 0 for label in LABELS}
    for item in assessments:
        expected_fields = (ASSESSMENT_FIELDS | {"coverage"} if coverage_reference
                           is not None else ASSESSMENT_FIELDS)
        if not isinstance(item, dict) or set(item) != expected_fields:
            raise ValueError("assessment fields are invalid")
        if any(not isinstance(item[field], str)
               for field in ("run_id", "case_id", "role", "review_digest")):
            raise ValueError("assessment identity is invalid")
        key = (item["run_id"], item["case_id"], item["role"])
        if key in seen or key not in eligible:
            raise ValueError("assessment is duplicate or has no successful review")
        seen.add(key)
        digest, count = eligible[key]
        if item["review_digest"] != digest:
            raise ValueError("assessment digest does not match the review")
        assessor = item["assessor"]
        if (not isinstance(assessor, str) or not 1 <= len(assessor.strip()) <= 80
                or any(ord(char) < 32 for char in assessor)):
            raise ValueError("assessor label is invalid")
        if (not isinstance(item["summary_grounded"], str)
                or item["summary_grounded"] not in LABELS):
            raise ValueError("summary grounding label is invalid")
        judgments = item["findings"]
        if not isinstance(judgments, list) or len(judgments) != count:
            raise ValueError("assessment needs one judgment per ordered finding")
        for judgment in judgments:
            if (not isinstance(judgment, dict) or
                    set(judgment) != {"grounded", "relevant"} or
                    any(not isinstance(judgment[field], str)
                        or judgment[field] not in LABELS
                        for field in ("grounded", "relevant"))):
                raise ValueError("finding judgment is invalid")
            for field in finding_labels:
                finding_labels[field][judgment[field]] += 1
        if coverage_reference is not None:
            expected_checks = coverage_reference.get((item["case_id"], item["role"]))
            coverage = item["coverage"]
            if (expected_checks is None or not isinstance(coverage, dict) or
                    set(coverage) != set(expected_checks) or
                    any(not isinstance(label, str) or label not in LABELS
                        for label in coverage.values())):
                raise ValueError("coverage judgments do not match reference checks")
            for label in coverage.values():
                coverage_labels[label] += 1
        summary_labels[item["summary_grounded"]] += 1

    return {
        "schema_version": "1.0",
        "eligible_reviews": len(eligible),
        "assessed_reviews": len(seen),
        "unassessed_reviews": len(eligible) - len(seen),
        "summary_grounded": summary_labels,
        "findings": finding_labels,
        "coverage": coverage_labels if coverage_reference is not None else None,
        "quality_score": None,
    }
