# SPDX-License-Identifier: GPL-3.0-or-later
"""Locale policy for numeric Qt controls.

The modelling UI accepts locale-aware text elsewhere, but numeric controls
must remain predictable for typed dimensions, shortcuts and settings.  Qt can
inherit a Thai/Arabic native-digit locale from Windows and render spin-box
values with those digits even when the application language is English.
"""
from __future__ import annotations

from PySide6.QtCore import QLocale


def use_ascii_numeric_locale(widget) -> None:
    """Force ASCII digits and ``.`` on a spin box or numeric line edit."""
    locale = QLocale(QLocale.C)
    widget.setLocale(locale)
    line_edit = getattr(widget, "lineEdit", lambda: None)()
    if line_edit is not None:
        line_edit.setLocale(locale)

