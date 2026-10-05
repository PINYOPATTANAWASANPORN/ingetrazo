# SPDX-License-Identifier: GPL-3.0-or-later
"""Small deterministic Assistant suggestions derived from document state."""
from __future__ import annotations

from core.layers import DEFAULT_LAYER

MAX_SUGGESTIONS = 4


def _item(label: str, prompt: str, goal: str, execution: str,
          scope: str) -> dict:
    return {"label": label, "prompt": prompt, "goal": goal,
            "execution": execution, "scope": scope}


def suggestions(scene, limit: int = MAX_SUGGESTIONS) -> list[dict]:
    """Return bounded local suggestions without a provider or prompt call.

    Only stable group/component selections produce selection-scoped chips;
    raw faces and edges cannot be represented by the current task contract.
    """
    limit = max(0, min(int(limit), MAX_SUGGESTIONS))
    groups = scene.groups_by_uid()
    selected = {id(entity) for entity in scene.selection}
    selected_groups = [group for group in groups.values()
                       if id(group) in selected]
    result: list[dict] = []
    if selected_groups:
        count = len(selected_groups)
        noun = "object" if count == 1 else "objects"
        result.extend([
            _item("Describe selection", f"Describe the selected {noun}.",
                  "explain", "analysis_only", "selection"),
            _item("Hide selection", f"Hide the selected {noun}.",
                  "revise", "apply_safe_changes", "selection"),
            _item("Lock selection", f"Lock the selected {noun}.",
                  "revise", "apply_safe_changes", "selection"),
        ])
        active = getattr(scene, "active_layer", None) or DEFAULT_LAYER
        if any((getattr(group, "layer", None) or DEFAULT_LAYER) != active
               for group in selected_groups):
            result.append(_item(
                "Assign active tag", f"Assign the active tag {active!r} to "
                f"the selected {noun}.", "revise", "apply_safe_changes",
                "selection"))
    elif groups:
        visible = sum(1 for group in groups.values()
                      if scene.entity_visible(group))
        result.extend([
            _item("Summarize model",
                  f"Summarize the visible model ({visible} objects).",
                  "explain", "analysis_only", "visible_model"),
            _item("Check model", "Check the visible model for hidden, locked, "
                  "or inconsistently tagged objects.", "check",
                  "analysis_only", "visible_model"),
            _item("Create test box", "Create a 1×1×1 m box named Test Box.",
                  "create", "apply_safe_changes", "visible_model"),
        ])
    else:
        result.extend([
            _item("Create room mass",
                  "Create a 4×4×3 m box named Room Mass.", "create",
                  "apply_safe_changes", "visible_model"),
            _item("Create column",
                  "Create a 0.30 m radius, 3 m high cylinder named Column.",
                  "create", "apply_safe_changes", "visible_model"),
            _item("Explain workspace",
                  "Explain the empty model and suggest a safe first step.",
                  "explain", "analysis_only", "visible_model"),
        ])
    return result[:limit]
