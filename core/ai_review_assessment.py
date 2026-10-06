# SPDX-License-Identifier: GPL-3.0-or-later
"""Validate human judgments bound to public-fixture specialist responses.

These labels measure assessed grounding and relevance, not completeness or an
overall quality score. The assessment file stores no reviewer prose.
"""
from __future__ import annotations

import re

from core import ai_review

LABELS = {"yes", "no", "unclear"}
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
ASSESSMENT_FIELDS = {"run_id", "case_id", "role", "review_digest", "assessor",
                     "summary_grounded", "findings"}


def summarize_assessments(records: list[dict], assessments: list[dict]) -> dict:
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
    for item in assessments:
        if not isinstance(item, dict) or set(item) != ASSESSMENT_FIELDS:
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
        summary_labels[item["summary_grounded"]] += 1

    return {
        "schema_version": "1.0",
        "eligible_reviews": len(eligible),
        "assessed_reviews": len(seen),
        "unassessed_reviews": len(eligible) - len(seen),
        "summary_grounded": summary_labels,
        "findings": finding_labels,
        "quality_score": None,
    }
