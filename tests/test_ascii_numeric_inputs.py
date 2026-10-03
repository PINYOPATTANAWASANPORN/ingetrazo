# SPDX-License-Identifier: GPL-3.0-or-later
"""Regression: English Preferences must not inherit native OS digits."""
import pytest
from PySide6.QtCore import QLocale, QSettings
from PySide6.QtWidgets import (
    QApplication, QDateEdit, QDoubleSpinBox, QSpinBox, QWidget,
)
from plugins import ascii_numeric_inputs as plugin
from views.preferences_dialog import PreferencesDialog
import views.preferences_dialog as prefs_mod


@pytest.fixture(autouse=True)
def isolate_installed_policy():
    """Other tests may already have loaded the bundled extension."""
    app = QApplication.instance()
    existing = getattr(app, "_ingetrazo_numeric_input_locale", None)
    if existing is not None:
        app.removeEventFilter(existing)
        del app._ingetrazo_numeric_input_locale
    yield
    if existing is not None:
        app._ingetrazo_numeric_input_locale = existing
        app.installEventFilter(existing)


@pytest.fixture
def policy():
    previous = QLocale()
    # Arabic explicitly exercises non-ASCII digits on every platform;
    # Thai native-digit substitution can also depend on Windows settings.
    QLocale.setDefault(QLocale("ar_EG"))
    plugin.setup(None)
    yield
    app = QApplication.instance()
    instance = app._ingetrazo_numeric_input_locale
    app.removeEventFilter(instance)
    del app._ingetrazo_numeric_input_locale
    instance.deleteLater()
    QLocale.setDefault(previous)


@pytest.mark.parametrize("locale_name", ["th_TH", "ar_EG", "fa_IR", "en_US", "de_DE"])
def test_display_input_and_locale_changes(policy, locale_name):
    parent = QWidget()
    parent.setLocale(QLocale(locale_name))
    integer = QSpinBox(parent)
    integer.setRange(-10000, 10000)
    integer.setValue(200)
    decimal = QDoubleSpinBox(parent)
    decimal.setRange(-10000, 10000)
    decimal.setDecimals(2)
    decimal.setValue(-1234.5)
    for widget in (integer, decimal):
        widget.ensurePolished()
        widget.setLocale(QLocale(locale_name))
    assert integer.text() == "200"
    assert decimal.text() == "-1234.50"
    decimal.lineEdit().setText("12.75")
    decimal.interpretText()
    assert decimal.value() == 12.75
    integer.stepUp()
    assert integer.value() == 201
    assert parent.locale() == QLocale(locale_name)
    parent.close()


def test_existing_widgets_and_idempotent_setup():
    widget = QSpinBox()
    widget.setLocale(QLocale("ar_EG"))
    widget.setValue(25)
    assert widget.text() != "25"
    plugin.setup(None)
    app = QApplication.instance()
    instance = app._ingetrazo_numeric_input_locale
    try:
        plugin.setup(None)
        assert app._ingetrazo_numeric_input_locale is instance
        assert widget.text() == "25"
        assert widget.value() == 25
    finally:
        app.removeEventFilter(instance)
        del app._ingetrazo_numeric_input_locale
        instance.deleteLater()
        widget.close()


def test_dates_and_default_locale_unchanged(policy):
    date = QDateEdit()
    date.setLocale(QLocale("th_TH"))
    date.ensurePolished()
    assert date.locale() == QLocale("th_TH")
    assert QLocale() == QLocale("ar_EG")
    date.close()


def test_preferences_values_and_save(policy, tmp_path, monkeypatch):
    path = str(tmp_path / "preferences.ini")
    monkeypatch.setattr(prefs_mod, "QSettings", lambda: QSettings(path, QSettings.IniFormat))
    from tests.test_preferences import _Win
    win = _Win()
    dialog = PreferencesDialog(win)
    for widget, value in ((dialog._autosave_min, 5),
                          (dialog._undo_steps, 200), (dialog._look_sens, 25)):
        widget.ensurePolished()
        widget.setValue(value)
        assert widget.cleanText() == str(value)
    dialog.accept()
    saved = QSettings(path, QSettings.IniFormat)
    assert int(saved.value("general/autosave_min")) == 5
    assert int(saved.value("walk/look_sensitivity")) == 25
    win.close()
