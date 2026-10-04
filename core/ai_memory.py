# SPDX-License-Identifier: GPL-3.0-or-later
"""Explicit, document-scoped facts supplied to AI tasks.

Project memory is intentionally small and human-owned.  Chat replies never
write it: the user edits the visible list, which travels with the ``.igz``
document and is copied into each task contract at creation time.
"""
from __future__ import annotations


MAX_FACTS = 20
MAX_FACT_LENGTH = 500
MAX_MEMORY_BYTES = 8192


def validate_memory(value) -> list[str]:
    """Return a clean copy of *value* or raise ``ValueError``.

    Empty lines are ignored and exact duplicates collapse while preserving
    order.  The bounds keep prompts predictable and prevent a document block
    from becoming an unbounded model-context channel.
    """
    if value is None:
        return []
    if not isinstance(value, (list, tuple)):
        raise ValueError("project memory must be a list of facts")
    if len(value) > MAX_FACTS:
        raise ValueError(f"project memory accepts at most {MAX_FACTS} facts")
    out: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = str(item).strip()
        if not text:
            continue
        if len(text) > MAX_FACT_LENGTH:
            raise ValueError(
                f"each project-memory fact must be at most {MAX_FACT_LENGTH} characters")
        if text not in seen:
            out.append(text)
            seen.add(text)
    if len("\n".join(out).encode("utf-8")) > MAX_MEMORY_BYTES:
        raise ValueError(
            f"project memory exceeds {MAX_MEMORY_BYTES} UTF-8 bytes")
    return out


def load_memory(value) -> list[str]:
    """Load a forward-compatible safe subset from an untrusted document."""
    if not isinstance(value, list):
        return []
    out: list[str] = []
    used = 0
    seen: set[str] = set()
    for item in value:
        if len(out) >= MAX_FACTS:
            break
        if not isinstance(item, str):
            continue
        text = item.strip()
        if not text or len(text) > MAX_FACT_LENGTH or text in seen:
            continue
        size = len(text.encode("utf-8")) + (1 if out else 0)
        if used + size > MAX_MEMORY_BYTES:
            break
        out.append(text)
        seen.add(text)
        used += size
    return out
