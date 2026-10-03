from PySide6.QtCore import QLocale
from PySide6.QtWidgets import QApplication, QSpinBox

from views.numeric_locale import use_ascii_numeric_locale


def test_numeric_controls_render_ascii_digits():
    app = QApplication.instance() or QApplication([])
    spin = QSpinBox()
    spin.setRange(0, 9999)
    use_ascii_numeric_locale(spin)
    spin.setValue(1234)

    assert spin.locale().language() == QLocale.Language.C
    assert spin.text() == "1234"
    assert spin.lineEdit().locale().language() == QLocale.Language.C
    app.processEvents()

