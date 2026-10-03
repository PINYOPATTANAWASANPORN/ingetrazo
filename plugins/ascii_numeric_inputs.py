# SPDX-License-Identifier: GPL-3.0-or-later
"""Use engineering notation (0-9 and a decimal point) in numeric inputs.

Qt otherwise inherits the OS number locale, independently of IngeTrazo's
UI language. Keep the policy local to spin boxes: dates, translations,
document geometry, and Windows regional settings are not changed.
"""
from PySide6.QtCore import QEvent, QLocale, QObject
from PySide6.QtWidgets import QApplication, QDoubleSpinBox, QSpinBox


class NumericInputLocale(QObject):
    def apply(self, widget: QObject) -> None:
        if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
            locale = QLocale.c()
            if widget.locale() != locale:
                widget.setLocale(locale)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        # Polish runs after construction, before first display. LocaleChange
        # also covers reparenting and explicit later locale changes.
        if event.type() in (QEvent.Type.Polish, QEvent.Type.LocaleChange):
            self.apply(watched)
        return False


def setup(app) -> None:
    """Normalize existing and future numeric inputs once per application."""
    application = QApplication.instance()
    if application is None:
        return
    if getattr(application, "_ingetrazo_numeric_input_locale", None) is not None:
        return
    policy = NumericInputLocale(application)
    application._ingetrazo_numeric_input_locale = policy
    application.installEventFilter(policy)
    for widget in application.allWidgets():
        policy.apply(widget)
