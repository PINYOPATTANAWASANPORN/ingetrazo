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
MAX_FILE_EVENTS = 10000
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_INPUT_BYTES = 32 * 1024 * 1024  # pretty-printed JSON may exceed canonical size
STATUSES = {"completed", "partial", "failed", "stale", "cancelled"}
EVENT_KEYS = {"sequence", "recorded_at", "task_id", "base_revision",
              "snapshot_id", "status", "report_digest", "previous_digest", "digest"}


def _digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _invalid(message):
    return {"ok": False, "code": "invalid_audit_bundle", "message": message}


def verify_bundle(bundle):
    """Verify a saved bundle independently of any live document or bridge."""
    if not isinstance(bundle, dict) or set(bundle) != {"payload", "integrity"}:
        return _invalid("Expected payload and integrity objects.")
    payload, integrity = bundle["payload"], bundle["integrity"]
    if (not isinstance(payload, dict) or set(payload) != {
            "schema_version", "exported_at", "session_only", "genesis_digest",
            "events", "total_events", "head_digest"} or
            not isinstance(integrity, dict) or set(integrity) != {
                "algorithm", "payload_digest", "signed"} or
            payload["schema_version"] != "1.0" or payload["session_only"] is not True or
            payload["genesis_digest"] != GENESIS or integrity["algorithm"] != "sha256" or
            integrity["signed"] is not False):
        return _invalid("Unsupported audit bundle format.")
    events = payload["events"]
    if (not isinstance(events, list) or len(events) > MAX_FILE_EVENTS or
            type(payload["total_events"]) is not int or
            payload["total_events"] != len(events) or
            not isinstance(payload["exported_at"], str)):
        return _invalid("Invalid event count or export time.")
    try:
        raw = canonical(payload)
    except (TypeError, ValueError, OverflowError):
        return _invalid("Invalid JSON values in audit bundle.")
    if len(raw) > MAX_FILE_BYTES or _digest(payload) != integrity["payload_digest"]:
        return _invalid("Audit payload checksum does not match.")
    previous = GENESIS
    for sequence, event in enumerate(events, 1):
        if (not isinstance(event, dict) or set(event) != EVENT_KEYS or
                type(event["sequence"]) is not int or event["sequence"] != sequence or
                type(event["base_revision"]) is not int or
                not all(isinstance(event[key], str) for key in (
                    "recorded_at", "task_id", "snapshot_id", "status",
                    "report_digest", "previous_digest", "digest")) or
                event["status"] not in STATUSES or
                event["previous_digest"] != previous or
                len(event["report_digest"]) != 64 or
                _digest({key: value for key, value in event.items()
                         if key != "digest"}) != event["digest"]):
            return _invalid(f"Audit chain breaks at event {sequence}.")
        previous = event["digest"]
    if payload["head_digest"] != previous:
        return _invalid("Audit head digest does not match.")
    return {"ok": True, "event_count": len(events), "head_digest": previous,
            "signed": False}


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

    def bundle(self):
        """Capture the complete in-memory trail for an explicit local save."""
        if len(self._events) > MAX_FILE_EVENTS:
            return {"ok": False, "code": "audit_too_large",
                    "message": "Audit has too many events for one file; page through MCP."}
        payload = {
            "schema_version": "1.0",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "session_only": True,
            "genesis_digest": GENESIS,
            "events": copy.deepcopy(self._events),
            "total_events": len(self._events),
            "head_digest": self._events[-1]["digest"] if self._events else GENESIS,
        }
        if len(canonical(payload)) > MAX_FILE_BYTES:
            return {"ok": False, "code": "audit_too_large",
                    "message": "Audit exceeds the maximum file size; page through MCP."}
        result = {"payload": payload, "integrity": {
            "algorithm": "sha256", "payload_digest": _digest(payload), "signed": False}}
        return {"ok": True, "bundle": result}
