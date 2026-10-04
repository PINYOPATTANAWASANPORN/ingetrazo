# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Consistent visible/locked tag labels across modelling controls."""
from __future__ import annotations

from core.i18n import tr


def layer_label(layer) -> str:
    """A tag name that also states every unavailable display state."""
    if not layer.visible and layer.locked:
        return tr("{name} (hidden, locked)", name=layer.name)
    if not layer.visible:
        return tr("{name} (hidden)", name=layer.name)
    if layer.locked:
        return tr("{name} (locked)", name=layer.name)
    return layer.name


def layer_tooltip(layer) -> str:
    """Explain what assigning entities to this tag will mean."""
    if not layer.visible and layer.locked:
        return tr("Hidden and locked — entities on this tag are invisible "
                  "and cannot be edited.")
    if not layer.visible:
        return tr("Hidden — entities moved to this tag will disappear from "
                  "the viewport.")
    if layer.locked:
        return tr("Locked — entities on this tag stay visible but cannot be "
                  "edited.")
    return tr("Visible and unlocked.")
