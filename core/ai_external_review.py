# SPDX-License-Identifier: GPL-3.0-or-later
"""Session-only MCP coordination of external read-only specialists.

The authenticated coordinator dispatches the returned snapshot itself. Role
tokens correlate submissions; they are not identities or isolated principals.
No provider credential, executor, or document write authority is involved.
"""
import copy
import json
import secrets

from core.ai_review import ROLES, snapshot, _parse, combine_reports

MAX_ACTIVE = 8
MAX_RETAINED = 64


def error(code, message):
    return {"ok": False, "code": code, "message": message}


class ExternalReviewService:
    def __init__(self, scene, tasks):
        self.scene = scene
        self.tasks = tasks
        self.reviews = {}

    def _current(self, review):
        if (review["packet"]["base_revision"] != self.scene.content_version
                and review["status"] not in {"stale", "cancelled"}):
            self._terminate(review, "stale")
        return review

    def _terminate(self, review, status):
        review.update(status=status, results={}, report=None)
        self.tasks.record_review(review["packet"]["task_id"], {
            "task_id": review["packet"]["task_id"], "status": status,
            "snapshot_id": review["packet"]["snapshot_id"],
            "base_revision": review["packet"]["base_revision"], "changed": False})

    def _public(self, review):
        packet = review["packet"]
        return copy.deepcopy({"ok": True, "review_id": review["review_id"],
            "task_id": packet["task_id"], "base_revision": packet["base_revision"],
            "snapshot_id": packet["snapshot_id"], "status": review["status"],
            "changed": False, "roles": {role: {"submitted": role in review["results"]}
                                        for role in ROLES},
            "report": review["report"]})

    def begin(self, task_id=""):
        task = self.tasks.get(task_id)
        if not task.get("ok"):
            return task
        for review in self.reviews.values():
            self._current(review)
            if review["packet"]["task_id"] == task_id:
                return self._dispatch_packet(review)
        if task["status"] not in {"ready", "running"}:
            return error("invalid_task_state", "create a new analysis-only task for this review")
        if sum(r["status"] == "collecting" for r in self.reviews.values()) >= MAX_ACTIVE:
            return error("review_limit", "cancel or finish an active review before starting another")
        try:
            packet = snapshot(self.scene, task)
        except (ValueError, TypeError) as exc:
            return error("invalid_review_scope", str(exc))
        if len(self.reviews) >= MAX_RETAINED:
            oldest = next(key for key, value in self.reviews.items()
                          if value["status"] != "collecting")
            old_task = self.tasks.task(self.reviews[oldest]["packet"]["task_id"])
            if old_task is not None:
                old_task.review = None
            del self.reviews[oldest]
        review_id = "review-" + secrets.token_hex(12)
        review = {"review_id": review_id, "packet": packet, "status": "collecting",
                  "tokens": {role: secrets.token_urlsafe(32) for role in ROLES},
                  "results": {}, "report": None}
        self.reviews[review_id] = review
        self.tasks.transition(task_id, "running")
        return self._dispatch_packet(review)

    def _dispatch_packet(self, review):
        public = self._public(review)
        if review["status"] == "collecting":
            public.update(snapshot=copy.deepcopy(review["packet"]), assignments=[
                {"role": role, "instructions": instruction,
                 "submission_token": review["tokens"][role]}
                for role, instruction in ROLES.items()])
        return public

    def get(self, review_id=""):
        review = self.reviews.get(str(review_id))
        if review is None:
            return error("unknown_review", "review is absent or expired from this bridge session")
        return self._public(self._current(review))

    def submit(self, review_id="", role="", submission_token="", snapshot_id="", result=None):
        review = self.reviews.get(str(review_id))
        if review is None:
            return error("unknown_review", "review is absent or expired from this bridge session")
        if not isinstance(role, str) or role not in ROLES:
            return error("invalid_role", "unknown specialist role")
        if (not isinstance(submission_token, str) or not submission_token.isascii() or
                not secrets.compare_digest(submission_token, review["tokens"][role])):
            return error("invalid_submission_token", "role submission token does not match")
        self._current(review)
        if review["status"] in {"stale", "cancelled"}:
            return error("review_" + review["status"], "create a new review task")
        if snapshot_id != review["packet"]["snapshot_id"]:
            return error("snapshot_mismatch", "submission must use the assigned snapshot")
        try:
            if isinstance(result, dict) and set(result) == {"error"}:
                message = result["error"]
                if not isinstance(message, str) or not 1 <= len(message) <= 300:
                    raise ValueError("error must contain 1-300 characters")
                parsed = {"role": role, "ok": False, "error": message}
            else:
                parsed = {"role": role, "ok": True, **_parse(
                    json.dumps(result, ensure_ascii=False, allow_nan=False), review["packet"])}
        except (ValueError, TypeError) as exc:
            return error("invalid_review_result", str(exc))
        if role in review["results"]:
            if review["results"][role] == parsed:
                return self._public(review)
            return error("submission_conflict", "this role already submitted a different result")
        review["results"][role] = parsed
        if len(review["results"]) == len(ROLES):
            report = combine_reports(review["packet"], [review["results"][r] for r in ROLES])
            review.update(status=report["status"], report=report)
            self.tasks.record_review(review["packet"]["task_id"], report)
        return self._public(review)

    def cancel(self, review_id=""):
        review = self.reviews.get(str(review_id))
        if review is None:
            return error("unknown_review", "review is absent or expired from this bridge session")
        self._current(review)
        if review["status"] == "collecting":
            self._terminate(review, "cancelled")
        return self._public(review)

    def export(self, review_id=""):
        current = self.get(review_id)
        if not current.get("ok"):
            return current
        return self.tasks.export_review(current["task_id"])
