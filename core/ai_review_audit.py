# SPDX-License-Identifier: GPL-3.0-or-later
"""Session-scoped, append-only metadata trail for specialist review outcomes.

The chain detects accidental modification of exported events. It is neither
persisted nor signed and is not evidence of provider identity.
"""
import copy
import hashlib
from datetime import datetime, timezone

from core.ai_review_export import canonical

GENESIS = "0" * 64
MAX_PAGE = 100
STATUSES = {"completed", "partial", "failed", "stale", "cancelled"}


class ReviewAuditTrail:
    def __init__(self):
        self._events = []
        self._last_by_task = {}

    def record(self, task, report):
        """Append one terminal state; identical retries do not create events."""
        status = report.get("status")
        if status not in STATUSES or report.get("task_id") != task.task_id:
            return
        report_digest = hashlib.sha256(canonical(report)).hexdigest()
        if self._last_by_task.get(task.task_id) == report_digest:
            return
        previous = self._events[-1]["digest"] if self._events else GENESIS
        event = {
            "sequence": len(self._events) + 1,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "task_id": task.task_id,
            "base_revision": task.base_revision,
            "snapshot_id": report.get("snapshot_id", ""),
            "status": status,
            "report_digest": report_digest,
            "previous_digest": previous,
        }
        event["digest"] = hashlib.sha256(canonical(event)).hexdigest()
        self._events.append(event)
        self._last_by_task[task.task_id] = report_digest

    def page(self, after_sequence=0, limit=MAX_PAGE):
        if (type(after_sequence) is not int or after_sequence < 0 or
                type(limit) is not int or not 1 <= limit <= MAX_PAGE):
            return {"ok": False, "code": "invalid_audit_page",
                    "message": "after_sequence must be nonnegative; limit must be 1-100"}
        if after_sequence > len(self._events):
            return {"ok": False, "code": "invalid_audit_page",
                    "message": "after_sequence exceeds the event count"}
        selected = self._events[after_sequence:after_sequence + limit]
        return copy.deepcopy({
            "ok": True, "schema_version": "1.0", "session_only": True,
            "signed": False, "genesis_digest": GENESIS,
            "events": selected, "total_events": len(self._events),
            "next_sequence": after_sequence + len(selected),
            "has_more": after_sequence + len(selected) < len(self._events),
            "head_digest": self._events[-1]["digest"] if self._events else GENESIS,
        })
