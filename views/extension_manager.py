# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Installed-extension inventory and enable/disable UI."""
from __future__ import annotations

import zipfile
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout,
)

from core.extensions import install_plugin, is_user_plugin, uninstall_plugin
from core.i18n import tr
from views.filedialogs import file_dialogs


class ExtensionManagerDialog(QDialog):
    """Show every discovered plugin, including disabled and broken ones."""

    def __init__(self, candidates, plugins, errors, disabled, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Extension Manager"))
        self.resize(760, 420)
        self._initial = set(disabled)
        self._candidates = {c.stem: c for c in candidates}
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

        actions = QHBoxLayout()
        self.install_button = QPushButton(tr("Install…"), self)
        self.remove_button = QPushButton(tr("Uninstall"), self)
        self.remove_button.setEnabled(False)
        self.install_button.clicked.connect(self._install)
        self.remove_button.clicked.connect(self._uninstall)
        self.tree.itemSelectionChanged.connect(self._sync_remove_button)
        actions.addWidget(self.install_button)
        actions.addWidget(self.remove_button)
        actions.addStretch(1)
        layout.addLayout(actions)

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

    def _selected_candidate(self):
        items = self.tree.selectedItems()
        if not items:
            return None
        stem = items[0].data(0, Qt.UserRole)
        return self._candidates.get(str(stem)) if stem else None

    def _sync_remove_button(self) -> None:
        candidate = self._selected_candidate()
        self.remove_button.setEnabled(
            candidate is not None and is_user_plugin(candidate.path))

    def _install(self) -> None:
        chosen, _selected_filter = file_dialogs.getOpenFileName(
            self, tr("Install extension"), "",
            tr("IngeTrazo extensions (*.py *.zip);;All files (*)"))
        if not chosen:
            return
        source = Path(chosen)
        try:
            target = install_plugin(source)
        except FileExistsError:
            answer = QMessageBox.question(
                self, tr("Update extension"),
                tr("An extension named “{name}” is already installed. "
                   "Replace it with this version?", name=source.stem),
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if answer != QMessageBox.Yes:
                return
            try:
                target = install_plugin(source, replace=True)
            except (OSError, ValueError, zipfile.BadZipFile) as exc:
                QMessageBox.warning(self, tr("Install extension"), str(exc))
                return
        except (OSError, ValueError, zipfile.BadZipFile) as exc:
            QMessageBox.warning(self, tr("Install extension"), str(exc))
            return
        QMessageBox.information(
            self, tr("Extension installed"),
            tr("“{name}” was installed. Restart IngeTrazo to load it.",
               name=target.stem))

    def _uninstall(self) -> None:
        candidate = self._selected_candidate()
        if candidate is None or not is_user_plugin(candidate.path):
            return
        answer = QMessageBox.question(
            self, tr("Uninstall extension"),
            tr("Remove “{name}” from this computer? The extension remains "
               "active until IngeTrazo restarts.", name=candidate.stem),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer != QMessageBox.Yes:
            return
        try:
            uninstall_plugin(candidate.path)
        except OSError as exc:
            QMessageBox.warning(self, tr("Uninstall extension"), str(exc))
            return
        item = self.tree.currentItem()
        if item is not None:
            self.tree.takeTopLevelItem(self.tree.indexOfTopLevelItem(item))
        self._candidates.pop(candidate.stem, None)
        self._sync_remove_button()
        QMessageBox.information(
            self, tr("Extension uninstalled"),
            tr("“{name}” was removed. Restart IngeTrazo to unload it.",
               name=candidate.stem))
