# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Installed-extension inventory and enable/disable UI."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QLabel, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout,
)

from core.i18n import tr


class ExtensionManagerDialog(QDialog):
    """Show every discovered plugin, including disabled and broken ones."""

    def __init__(self, candidates, plugins, errors, disabled, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Extension Manager"))
        self.resize(760, 420)
        self._initial = set(disabled)
        loaded = {p.stem for p in plugins}
        failed = {e.stem: e.error for e in errors}

        layout = QVBoxLayout(self)
        intro = QLabel(tr(
            "Enable or disable installed extensions. Changes take effect "
            "the next time IngeTrazo starts."), self)
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.tree = QTreeWidget(self)
        self.tree.setObjectName("extensionManagerTree")
        self.tree.setHeaderLabels([
            tr("Extension"), tr("Status"), tr("Location")])
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        for candidate in candidates:
            stem = candidate.stem
            if stem in self._initial:
                status = tr("Disabled")
            elif stem in failed:
                status = tr("Load error")
            elif stem in loaded:
                status = tr("Loaded")
            else:
                status = tr("No tools registered")
            item = QTreeWidgetItem([
                stem, status, str(candidate.path.parent)])
            item.setData(0, Qt.UserRole, stem)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(
                0, Qt.Unchecked if stem in self._initial else Qt.Checked)
            if stem in failed:
                item.setToolTip(1, failed[stem])
            self.tree.addTopLevelItem(item)
        self.tree.resizeColumnToContents(0)
        self.tree.resizeColumnToContents(1)
        layout.addWidget(self.tree, 1)

        if not candidates:
            empty = QTreeWidgetItem([tr("No extensions installed"), "", ""])
            empty.setFlags(Qt.NoItemFlags)
            self.tree.addTopLevelItem(empty)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel, parent=self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def disabled_stems(self) -> set[str]:
        disabled = set()
        for row in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(row)
            stem = item.data(0, Qt.UserRole)
            if stem and item.checkState(0) != Qt.Checked:
                disabled.add(str(stem))
        return disabled

    def changed(self) -> bool:
        return self.disabled_stems() != self._initial
