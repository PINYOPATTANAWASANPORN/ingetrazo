# SPDX-License-Identifier: GPL-3.0-or-later
"""Versioned, allowlisted review exports; no live settings or role tokens."""
import hashlib
import json
from datetime import datetime, timezone

from core.ai_review import ROLES, combine_reports


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def export_review(task, current_revision):
    report = task.get("review")
    if not report or task.get("status") not in {"completed", "partial", "failed"}:
        return {"ok": False, "code": "review_not_exportable",
                "message": "No finished review is available for this task."}
    if (task.get("base_revision") != current_revision or
            report.get("base_revision") != current_revision):
        return {"ok": False, "code": "stale_review",
                "message": "The document changed; run the review again before exporting."}
    if report.get("task_id") != task.get("task_id"):
        return {"ok": False, "code": "review_mismatch", "message": "Review task identity does not match."}
    # Reconstruct structured fields instead of serializing task/settings objects.
    specialists = []
    for entry in report.get("specialists", []):
        if entry.get("role") not in ROLES:
            continue
        cleaned = {k: entry[k] for k in ("role", "ok", "provider", "model") if k in entry}
        if entry["ok"]:
            cleaned["summary"] = entry["summary"]
            cleaned["findings"] = [{k: finding[k] for k in
                ("entity_id", "topic", "verdict", "evidence")}
                for finding in entry["findings"]]
        else:
            cleaned["error"] = entry["error"]
        specialists.append(cleaned)
    if {r["role"] for r in specialists} != set(ROLES) or len(specialists) != 2:
        return {"ok": False, "code": "incomplete_review", "message": "Both role outcomes are required."}
    packet = {k: report[k] for k in ("task_id", "base_revision", "snapshot_id")}
    packet["limitations"] = ["Metadata-only advisory review; not geometry or regulatory certification.",
                            "Model names identify requested models, not attested execution."]
    cleaned = combine_reports(packet, specialists)
    payload = {"schema_version": "1.0", "exported_at": datetime.now(timezone.utc).isoformat(),
               "current_revision": current_revision, "report": cleaned}
    digest = hashlib.sha256(canonical(payload)).hexdigest()
    return {"ok": True, "bundle": {"payload": payload,
            "integrity": {"algorithm": "sha256", "payload_digest": digest,
                          "signed": False}}}
