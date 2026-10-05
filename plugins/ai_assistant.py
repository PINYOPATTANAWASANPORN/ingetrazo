# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Asistente IA — model with AI from INSIDE IngeTrazo, in the side tray's
«AI» tab (Ctrl+Shift+A brings it forward, even when hidden).

The user types what they want; the model answers in Spanish. Existing entity
properties use typed JSON proposals that the user previews and explicitly
applies or discards. Unsupported geometry creation can still use ONE
```python recipe per turn through the transactional executor (core.ai).

Providers follow the IngePresupuestos convention the user already knows:
paste ONE API key and the provider is detected by its prefix (gsk_ → Groq,
sk-ant- → Anthropic, AIza → Gemini, sk-or- → OpenRouter, sk- → OpenAI), or
leave it empty for a local Ollama. Model name and Ollama URL are editable;
everything persists in QSettings. Network calls run on a worker thread —
the recipes always execute on the Qt main thread.
"""
from __future__ import annotations

import base64
import json
import threading
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, QSaveFile, QSettings, QTimer, Qt, Signal
from PySide6.QtGui import QFontDatabase, QImageReader, QPalette
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core import ai, ai_context, ai_recipes, ai_suggestions
from core.i18n import tr
from views.filedialogs import file_dialogs
from views.fold_section import FoldSection, narrow, wrapping_form

MAX_ROUNDS = 12

#: Reply budget per turn. 4096 was not enough for chatty coders (gemini
#: 2.5 flash got cut mid-```python and the loop ended with nothing drawn);
#: every provider we speak accepts 8192 output tokens.
MAX_TOKENS = 8192

#: Gemini 2.5 models bill their hidden "thinking" against the SAME
#: max_tokens — flash kept getting cut even at 8192 (seen live modeling a
#: fountain). Both 2.5 flash and pro accept 16384.
TOKENS_BY_PROVIDER = {"gemini": 16384}

#: The assistant's own voice and its one-block-per-reply contract; the
#: modelling reference itself is shared with the MCP door (core.ai_recipes),
#: so a new helper is taught once and both doors learn it.
SYSTEM_PROMPT = "\n".join((
    "Eres el asistente de modelado de IngeTrazo. " + ai_recipes.UNITS
    + " Conversas en español, breve y claro.",
    """
    Para cambiar propiedades de grupos o componentes existentes, responde \
con EXACTAMENTE UN bloque ```json y nada de Python, con esta forma estricta: \
{"actions":[...]}. Acciones admitidas: \
{"action":"rename_entities","entity_ids":["id"],"name":"Nombre"}; \
{"action":"set_visibility","entity_ids":["id"],"visible":true}; \
{"action":"set_lock","entity_ids":["id"],"locked":true}; \
{"action":"assign_tag","entity_ids":["id"],"tag":"Etiqueta"}; \
{"action":"assign_material","entity_ids":["id"],"material":"Material"}; \
{"action":"transform_entities","entity_ids":["id"],"operation":"translate",\
"delta":[x,y,z]}. rotate usa center, axis y degrees; scale usa center y \
factor (número o vector de tres números). Usa solo entity_ids del contrato. \
El programa validará el bloque y mostrará una vista previa que el usuario \
debe aprobar; nunca afirmes que ya se aplicó.

Para crear cajas usa create_box con name, origin, size, tag/material opcionales \
y component booleano. Para cilindros usa create_cylinder con name, origin, \
radius, height, segments, tag/material opcionales y component booleano. \
create_slab usa name, origin y size=[ancho,fondo,espesor]. create_wall usa \
name, start=[x,y,z], end=[x,y,z] a la misma altura, height, thickness y \
openings opcional: [{offset,sill,width,height}]. El espesor crece a la izquierda \
de start->end; sill=0 es puerta. Los huecos deben caber dentro sin tocarse. \
create_component_instance usa name, source_id de un componente de nivel \
superior y offset=[x,y,z]; conserva la definición compartida. \
Las coordenadas son model por defecto. Para crear dentro de un contenedor \
Group con matriz usa coordinate_space=parent y parent_id explícito del \
alcance. No se admite un padre dentro de una definición Component compartida \
ni crear durante edición de grupo. Nunca amplíes el alcance para evitar un error.

Para una operación aún no admitida por esas acciones, y SOLO cuando el \
contrato indique raw_python_allowed=true, incluye EXACTAMENTE UN bloque \
```python por respuesta. Tras ejecutarlo \
recibirás stdout/errores y, si está disponible, una captura del viewport. \
No mezcles bloques JSON y Python. Cuando el pedido esté terminado, responde \
sin bloques con un resumen corto. Sin un bloque no se ejecuta nada: nunca \
describas como hecho lo que no has ejecutado.""".strip(),
    ai_recipes.SCOPE,
    ai_recipes.RECIPES,
    ai_recipes.HOW_IT_RUNS.format(unit="bloque"),
    """El código de tus recetas viejas se resume como "[receta ya \
ejecutada]"; su efecto sigue en el modelo.

Si el usuario adjunta una FOTO de un objeto (una fuente, un mueble, una \
fachada): identifica sus partes y proporciones y recréalo por partes, cada \
una como grupo con nombre. Una foto NO trae medidas: usa las que el usuario \
dé y declara como supuesto toda dimensión que estimes de la imagen. Para \
piezas torneadas (platos, columnas, jarrones) usa revolve(). Compara tus \
capturas contra la foto e itera hasta que la silueta calce.""",
))


_BUILD_WORDS = ("dibuj", "crea", "haz", "hac", "modela", "constru", "añad",
                "agreg", "pon", "gener", "diseñ", "levant", "arma", "traza",
                "draw", "build", "make", "create", "add")


def _asks_to_build(prompt: str) -> bool:
    """Whether the user's message asks for something to be modelled (so a
    reply without code is a model that did not do its job)."""
    low = (prompt or "").lower()
    return any(w in low for w in _BUILD_WORDS)


class PromptEdit(QPlainTextEdit):
    """The prompt: several lines, Enter sends, Shift+Enter breaks a line.
    ``text``/``setText`` as the one-line field it replaces had."""
    submitted = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setTabChangesFocus(True)
        line = self.fontMetrics().lineSpacing()
        self.setMinimumHeight(2 * line + 12)

    def keyPressEvent(self, ev) -> None:
        if (ev.key() in (Qt.Key_Return, Qt.Key_Enter)
                and not ev.modifiers() & (Qt.ShiftModifier
                                          | Qt.ControlModifier)):
            self.submitted.emit()
            return
        super().keyPressEvent(ev)

    def text(self) -> str:
        return self.toPlainText()

    def setText(self, text: str) -> None:
        self.setPlainText(text)


class ProjectMemoryDialog(QDialog):
    """Visible editor for durable, document-owned AI facts."""

    def __init__(self, facts, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Project AI memory"))
        self.resize(520, 340)
        layout = QVBoxLayout(self)
        label = QLabel(tr(
            "One fact per line. These facts are saved in this document and "
            "included in every new AI task. Chat cannot change them."))
        label.setWordWrap(True)
        layout.addWidget(label)
        self.editor = QPlainTextEdit()
        self.editor.setPlainText("\n".join(facts))
        self.editor.setPlaceholderText(tr(
            "Typical floor height is 3.00 m\nPreferred wall thickness is 0.15 m"))
        layout.addWidget(self.editor, 1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel, parent=self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def facts(self) -> list[str]:
        return self.editor.toPlainText().splitlines()


class SpecialistModelsDialog(QDialog):
    """Role-specific provider and model choices; credentials stay in connection settings."""

    def __init__(self, provider, models, parent=None, role_providers=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Specialist models"))
        layout = QVBoxLayout(self)
        label = QLabel(tr("Choose a provider for each reviewer. Other providers use API keys already saved in the main connection settings. Leave the model blank to use that provider's saved or default model."))
        label.setWordWrap(True)
        layout.addWidget(label)
        self.editors = {}
        self.provider_selectors = {}
        role_providers = role_providers or {}
        for role, title in (("model_structure", tr("Model structure")),
                            ("task_requirements", tr("Task requirements"))):
            layout.addWidget(QLabel(title))
            selector = QComboBox()
            selector.addItem(tr("Same as Assistant ({provider})", provider=provider), "")
            for choice in ai.PROVIDERS:
                selector.addItem(ai.PROVIDER_INFO[choice][0], choice)
            selector.setCurrentIndex(max(0, selector.findData(role_providers.get(role, ""))))
            layout.addWidget(selector)
            self.provider_selectors[role] = selector
            editor = QLineEdit(models.get(role, ""))
            editor.setMaxLength(200)
            editor.setPlaceholderText(tr("Use selected provider's saved/default model"))
            layout.addWidget(editor)
            self.editors[role] = editor
            selector.currentIndexChanged.connect(lambda _index, field=editor: field.clear())
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def models(self):
        return {role: editor.text().strip() for role, editor in self.editors.items()}

    def providers(self):
        return {role: selector.currentData() or ""
                for role, selector in self.provider_selectors.items()}


class AsistentePanel(QWidget):
    """The assistant as the «AI» tab of the side tray: the connection
    settings fold away, the chat takes the rest of the height."""
    _reply = Signal(object)     # object, not dict: queued dicts get COPIED

    def __init__(self, viewport, parent=None) -> None:
        super().__init__(parent)
        self._viewport = viewport
        self._scope: dict = {"__name__": "__ai__"}
        self._convo: list[dict] = []
        self._busy = False
        self._round = 0
        self._nudged = False
        self._last_prompt = ""
        self._tasks = None
        self._changes = None
        self._task_packet: dict | None = None
        self._active_task_id = ""
        self._task_changed = False
        self._analysis_nudged = False
        self._python_nudged = False
        self._generation = 0
        self._cancel_token = None
        self._review_role_connections = {}
        self._stream_text = ""
        self._stream_flush_scheduled = False
        self._suggestions: list[dict] = []
        self._suggestion_signature = None
        self._pending_task_id = ""
        self._pending_idempotency_key = ""
        self._foto: tuple[str, str, str] | None = None  # (b64, mime, name)
        self._reply.connect(self._on_reply, Qt.QueuedConnection)
        self._build_ui()
        self._viewport.sceneVersionChanged.connect(
            lambda _version: self._refresh_context_controls())
        self._load_settings()
        self._suggestion_timer = QTimer(self)
        self._suggestion_timer.setInterval(500)
        self._suggestion_timer.timeout.connect(
            self._refresh_suggestions_if_needed)
        self._suggestion_timer.start()
        self._refresh_suggestions(force=True)

    # ---- UI -----------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 0)

        conn = FoldSection(tr("AI Assistant — connection"),
                           "ia/open_connection")
        self._connection = conn
        form = wrapping_form(conn.body)
        self._provider = QComboBox()
        self._provider.addItem(tr("Auto (by key prefix)"), "auto")
        for prov in ai.PROVIDERS:
            self._provider.addItem(ai.PROVIDER_INFO[prov][0], prov)
        self._provider.currentIndexChanged.connect(self._on_provider_changed)
        form.addRow(tr("Provider:"), self._provider)

        self._key = QLineEdit()
        self._key.setEchoMode(QLineEdit.Password)
        self._key.setPlaceholderText(tr("empty = local AI (Ollama, LM Studio)"))
        self._key.textChanged.connect(self._on_key_changed)
        self._key.editingFinished.connect(self._save_settings)
        form.addRow(tr("API key:"), self._key)

        self._key_link = QLabel("")
        self._key_link.setOpenExternalLinks(True)
        self._key_link.setWordWrap(True)
        form.addRow(self._key_link)

        self._model = QComboBox()
        self._model.setEditable(True)
        self._model.setInsertPolicy(QComboBox.NoInsert)
        self._model.lineEdit().setPlaceholderText(
            tr("model (default per provider)"))
        self._model.lineEdit().editingFinished.connect(self._save_settings)
        form.addRow(tr("Model:"), self._model)

        buttons = QHBoxLayout()
        self._modelos = QPushButton(tr("Models"))
        self._modelos.setToolTip(
            tr("List the models your key can use"))
        self._modelos.clicked.connect(self._on_modelos)
        buttons.addWidget(self._modelos)
        self._probar = QPushButton(tr("Test connection"))
        self._probar.clicked.connect(self._on_probar)
        buttons.addWidget(self._probar)
        form.addRow(buttons)
        self._specialist_models = QPushButton(tr("Specialist connections…"))
        self._specialist_models.setToolTip(tr("Choose a provider and model for each read-only reviewer"))
        self._specialist_models.clicked.connect(self._on_specialist_models)
        form.addRow(self._specialist_models)

        self._ollama = QLineEdit("http://localhost:11434")
        self._ollama.setToolTip(tr("Local AI server — Ollama: http://localhost:11434, LM Studio: http://localhost:1234 (key left empty)"))
        self._ollama.editingFinished.connect(self._save_settings)
        self._ollama_label = QLabel(tr("Server:"))
        form.addRow(self._ollama_label, self._ollama)

        self._shots = QCheckBox(tr("Send viewport screenshots to the model"))
        self._shots.setChecked(True)
        self._shots.toggled.connect(lambda _on: self._save_settings())
        form.addRow(self._shots)
        self._allow_python = QCheckBox(tr(
            "Allow advanced Python recipes for this session"))
        self._allow_python.setToolTip(tr(
            "Python runs inside IngeTrazo. Leave this off for typed, previewed changes."))
        form.addRow(self._allow_python)
        narrow(self._provider, self._model, self._key, self._ollama,
               self._shots, self._allow_python, self._modelos, self._probar)
        layout.addWidget(conn)

        self._chat = QTextEdit()
        self._chat.setReadOnly(True)
        self._chat.setFont(
            QFontDatabase.systemFont(QFontDatabase.FixedFont))
        self._chat.setMinimumHeight(80)

        # The prompt under the chat, with a handle between them to give it
        # more room (Marco: «ese espacio es muy pequeño para un prompt»).
        bottom = QWidget()
        bl = QVBoxLayout(bottom)
        bl.setContentsMargins(0, 0, 0, 0)
        chip_row = QHBoxLayout()
        self._foto_chip = QLabel("")
        chip_row.addWidget(self._foto_chip, 1)
        narrow(self._foto_chip)
        self._foto_quitar = QPushButton("✕")
        self._foto_quitar.setFixedWidth(28)
        self._foto_quitar.setToolTip(tr("Remove the photo"))
        self._foto_quitar.clicked.connect(self._clear_foto)
        chip_row.addWidget(self._foto_quitar)
        bl.addLayout(chip_row)

        intent_row = QHBoxLayout()
        self._intent_scope = QComboBox()
        for label, value in ((tr("Auto scope"), "auto"),
                             (tr("Selection"), "selection"),
                             (tr("Current group"), "current_group"),
                             (tr("Visible model"), "visible_model"),
                             (tr("Whole model"), "whole_model")):
            self._intent_scope.addItem(label, value)
        self._intent_scope.setToolTip(tr(
            "What the assistant may consider for this request"))
        intent_row.addWidget(self._intent_scope)
        self._intent_goal = QComboBox()
        self._intent_goal.addItem(tr("Auto goal"), "")
        for label, value in ((tr("Create"), "create"),
                             (tr("Revise"), "revise"),
                             (tr("Furnish"), "furnish"),
                             (tr("Check"), "check"),
                             (tr("Quantify"), "quantify"),
                             (tr("Explain"), "explain")):
            self._intent_goal.addItem(label, value)
        self._intent_goal.setToolTip(tr(
            "The result you want; Auto infers it from your short request"))
        intent_row.addWidget(self._intent_goal)
        self._intent_mode = QComboBox()
        self._intent_mode.addItem(tr("Act (undoable)"), "apply_safe_changes")
        self._intent_mode.addItem(tr("Analysis only"), "analysis_only")
        self._intent_mode.setToolTip(tr(
            "Analysis only blocks any Python recipe returned by the model"))
        intent_row.addWidget(self._intent_mode)
        bl.addLayout(intent_row)
        self._specialist_review = QCheckBox(tr("Review with 2 specialists (read-only)"))
        self._specialist_review.setToolTip(tr(
            "Sends two independent requests using the selected provider and each specialist's model choice, with the same scoped metadata. No model changes."))
        self._specialist_review.toggled.connect(self._on_review_mode)
        bl.addWidget(self._specialist_review)

        memory_row = QHBoxLayout()
        self._intent_assumptions = QLineEdit()
        self._intent_assumptions.setPlaceholderText(tr(
            "Assumptions (optional; separate with semicolons)"))
        self._intent_assumptions.setToolTip(tr(
            "Visible task assumptions sent to the model; they are not saved automatically"))
        memory_row.addWidget(self._intent_assumptions, 1)
        self._project_memory = QPushButton()
        self._project_memory.setToolTip(tr(
            "Edit explicit project facts saved in this document"))
        self._project_memory.clicked.connect(self._on_project_memory)
        memory_row.addWidget(self._project_memory)
        self._export_review = QPushButton(tr("Export review…"))
        self._export_review.setEnabled(False)
        self._export_review.setToolTip(tr(
            "Available after a two-specialist review finishes for the current model revision"))
        self._export_review.clicked.connect(self._on_export_review)
        bl.addLayout(memory_row)
        bl.addWidget(self._export_review)
        self._review_export_hint = QLabel(tr(
            "Run a two-specialist review to enable Export review."))
        self._review_export_hint.setWordWrap(True)
        bl.addWidget(self._review_export_hint)
        audit_row = QHBoxLayout()
        self._export_audit = QPushButton(tr("Export review history…"))
        self._export_audit.setEnabled(False)
        self._export_audit.clicked.connect(self._on_export_audit)
        audit_row.addWidget(self._export_audit)
        self._verify_audit = QPushButton(tr("Verify history file…"))
        self._verify_audit.clicked.connect(self._on_verify_audit)
        audit_row.addWidget(self._verify_audit)
        audit_row.addStretch()
        bl.addLayout(audit_row)
        self._refresh_project_memory()
        suggestion_row = QGridLayout()
        suggestion_row.setContentsMargins(0, 0, 0, 0)
        suggestion_row.addWidget(QLabel(tr("Try:")), 0, 0)
        self._suggestion_buttons = []
        for index in range(ai_suggestions.MAX_SUGGESTIONS):
            button = QPushButton()
            button.clicked.connect(
                lambda _checked=False, i=index: self._apply_suggestion(i))
            suggestion_row.addWidget(button, index + 1, 0)
            self._suggestion_buttons.append(button)
        suggestion_row.setColumnStretch(0, 1)
        self._suggestion_bar = QWidget()
        self._suggestion_bar.setLayout(suggestion_row)
        bl.addWidget(self._suggestion_bar)
        self._task_chip = QLabel("")
        self._task_chip.setVisible(False)
        bl.addWidget(self._task_chip)
        self._stream_preview = QPlainTextEdit()
        self._stream_preview.setReadOnly(True)
        self._stream_preview.setMaximumHeight(120)
        self._stream_preview.setPlaceholderText(tr("AI response in progress…"))
        self._stream_preview.setVisible(False)
        bl.addWidget(self._stream_preview)
        self._change_preview = QPlainTextEdit()
        self._change_preview.setReadOnly(True)
        self._change_preview.setMaximumHeight(120)
        self._change_preview.setVisible(False)
        bl.addWidget(self._change_preview)
        preview_row = QHBoxLayout()
        self._apply_changes = QPushButton(tr("Apply changes"))
        self._apply_changes.clicked.connect(self._on_apply_typed_changes)
        self._discard_changes = QPushButton(tr("Discard"))
        self._discard_changes.clicked.connect(self._on_discard_typed_changes)
        preview_row.addWidget(self._apply_changes)
        preview_row.addWidget(self._discard_changes)
        preview_row.addStretch()
        self._preview_buttons = QWidget()
        self._preview_buttons.setLayout(preview_row)
        self._preview_buttons.setVisible(False)
        bl.addWidget(self._preview_buttons)
        narrow(self._intent_scope, self._intent_goal, self._intent_mode,
               self._intent_assumptions,
               *self._suggestion_buttons,
               self._task_chip, self._stream_preview, self._change_preview,
               self._apply_changes, self._discard_changes)

        self._input = PromptEdit()
        self._input.setPlaceholderText(
            tr("e.g. draw a 6×4 m house with a gable roof")
            + "\n" + tr("Enter sends · Shift+Enter: new line"))
        self._input.submitted.connect(self._on_send)
        bl.addWidget(self._input, 1)

        split = QSplitter(Qt.Vertical)
        split.setChildrenCollapsible(False)
        split.addWidget(self._chat)
        split.addWidget(bottom)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 1)
        line = self._input.fontMetrics().lineSpacing()
        split.setSizes([400, 10 * line + 24])
        layout.addWidget(split, 1)

        row3 = QHBoxLayout()
        self._adjuntar = QPushButton(tr("Photo…"))
        self._adjuntar.setToolTip(tr(
            "Attach a photo — the model recreates what it shows "
            "(give it the real measurements)"))
        self._adjuntar.clicked.connect(self._on_foto)
        row3.addWidget(self._adjuntar)
        row3.addStretch()
        self._cancel = QPushButton(tr("Cancel"))
        self._cancel.setToolTip(tr(
            "Stop the current AI response; partial output will not be executed"))
        self._cancel.clicked.connect(self._on_cancel)
        self._cancel.setVisible(False)
        row3.addWidget(self._cancel)
        self._send = QPushButton(tr("Send"))
        self._send.clicked.connect(self._on_send)
        row3.addWidget(self._send)
        layout.addLayout(row3)
        self._clear_foto()

    def focus_input(self) -> None:
        self._refresh_context_controls()
        self._input.setFocus(Qt.ShortcutFocusReason)

    def _chat_colors(self) -> dict:
        """Text colors that read on the CURRENT theme — hardcoded
        light-theme grays vanish on a dark chat background (user report)."""
        dark = self.palette().color(QPalette.ColorRole.Base).lightness() < 128
        if dark:
            return {"user": "#7ab7ff", "ai": "#e8eaed", "muted": "#9aa5b1",
                    "ok": "#7ce0a3", "err": "#ff8f8f"}
        return {"user": "#2b6cb0", "ai": "#1a202c", "muted": "#718096",
                "ok": "#2f855a", "err": "#c53030"}

    def _append(self, text: str, role: str) -> None:
        color = self._chat_colors()[role]
        self._chat.append(f'<pre style="color:{color}; white-space:pre-wrap; '
                          f'margin:2px">{_esc(text)}</pre>')
        self._chat.verticalScrollBar().setValue(
            self._chat.verticalScrollBar().maximum())

    # ---- Settings -----------------------------------------------------------
    def _settings(self) -> QSettings:
        return QSettings()

    def _load_settings(self) -> None:
        self._loading = True
        try:
            self._read_settings()
        finally:
            self._loading = False

    def _read_settings(self) -> None:
        st = self._settings()
        self._key.setText(str(st.value("ia/api_key", "") or ""))
        self._model.setEditText(str(st.value("ia/modelo", "") or ""))
        self._ollama.setText(str(st.value("ia/ollama_url",
                                          "http://localhost:11434") or ""))
        self._shots.setChecked(str(st.value("ia/capturas", "1")) != "0")
        for combo, key, default in (
                (self._intent_scope, "ia/task_scope", "auto"),
                (self._intent_goal, "ia/task_goal", ""),
                (self._intent_mode, "ia/task_mode", "apply_safe_changes")):
            index = combo.findData(str(st.value(key, default) or default))
            if index >= 0:
                combo.setCurrentIndex(index)
        stored = str(st.value("ia/proveedor", "auto") or "auto")
        idx = self._provider.findData(stored)
        if idx >= 0:
            self._provider.setCurrentIndex(idx)
        self._on_key_changed()

    def _save_settings(self) -> None:
        if getattr(self, "_loading", False):
            return
        st = self._settings()
        st.setValue("ia/api_key", self._key.text())
        st.setValue("ia/modelo", self._model.currentText().strip())
        st.setValue("ia/ollama_url", self._ollama.text().strip())
        st.setValue("ia/capturas", "1" if self._shots.isChecked() else "0")
        st.setValue("ia/proveedor", self._provider.currentData())
        st.setValue("ia/task_scope", self._intent_scope.currentData())
        goal, mode = (self._review_previous if self._specialist_review.isChecked()
                      else (self._intent_goal.currentData(), self._intent_mode.currentData()))
        st.setValue("ia/task_goal", goal)
        st.setValue("ia/task_mode", mode)
        self._stash_credentials(st, self._provider.currentData())

    def _task_service(self):
        if self._tasks is None or self._tasks.scene is not self._viewport.scene:
            from core.ai_tasks import AITaskService
            self._tasks = AITaskService(self._viewport.scene)
        return self._tasks

    def _change_service(self):
        tasks = self._task_service()
        if (self._changes is None
                or self._changes.scene is not self._viewport.scene
                or self._changes.history is not self._viewport.history
                or self._changes.tasks is not tasks):
            from core.ai_changes import AIChangeService
            self._changes = AIChangeService(
                self._viewport.scene, self._viewport.history, tasks)
        return self._changes

    def _create_task(self, prompt: str) -> dict:
        assumptions = [item.strip() for item in
                       self._intent_assumptions.text().split(";")
                       if item.strip()]
        return self._task_service().create(
            intent=prompt, scope=self._intent_scope.currentData(),
            goal="check" if self._specialist_review.isChecked() else self._intent_goal.currentData(), constraints={},
            execution="analysis_only" if self._specialist_review.isChecked() else self._intent_mode.currentData(),
            assumptions=assumptions, acceptance_criteria=[])

    def _set_task_controls_enabled(self, enabled: bool) -> None:
        for widget in (self._intent_scope, self._intent_goal,
                       self._intent_mode, self._intent_assumptions,
                       self._project_memory, self._allow_python,
                       self._suggestion_bar, self._specialist_review,
                       self._specialist_models):
            widget.setEnabled(enabled)
        if self._specialist_review.isChecked():
            self._intent_goal.setEnabled(False)
            self._intent_mode.setEnabled(False)
            self._suggestion_bar.setEnabled(False)

    def _on_review_mode(self, checked):
        if checked:
            self._review_previous = (self._intent_goal.currentData(),
                                     self._intent_mode.currentData())
            self._intent_goal.setCurrentIndex(self._intent_goal.findData("check"))
            self._intent_mode.setCurrentIndex(self._intent_mode.findData("analysis_only"))
        else:
            goal, mode = self._review_previous
            self._intent_goal.setCurrentIndex(self._intent_goal.findData(goal))
            self._intent_mode.setCurrentIndex(self._intent_mode.findData(mode))
        self._set_task_controls_enabled(not self._busy and not self._pending_task_id)

    def _refresh_context_controls(self) -> None:
        self._refresh_review_export()
        self._refresh_project_memory()
        self._refresh_suggestions(force=True)

    def _refresh_review_export(self):
        if hasattr(self, "_export_review"):
            available = (not self._busy and bool(self._active_task_id) and
                         self._task_service().export_review(self._active_task_id).get("ok"))
            self._export_review.setEnabled(bool(available))
            self._review_export_hint.setVisible(not available and not self._busy)
            self._export_audit.setEnabled(not self._busy and bool(
                self._task_service().review_audit(limit=1)["total_events"]))

    def _on_export_review(self):
        if self._busy or not self._active_task_id:
            return
        service, task_id = self._task_service(), self._active_task_id
        result = service.export_review(task_id)
        if not result.get("ok"):
            self._append(result["message"], "err")
            return
        path, _ = QFileDialog.getSaveFileName(self, tr("Export review"),
                                             "ai-review.json", "JSON (*.json)")
        if not path:
            return
        # Modal dialogs process events: recheck document identity and revision.
        if service is not self._task_service() or task_id != self._active_task_id:
            self._append(tr("The document or task changed; run the review again."), "err")
            return
        result = service.export_review(task_id)
        if not result.get("ok"):
            self._append(result["message"], "err")
            return
        self._save_json_bundle(path, result["bundle"])

    def _save_json_bundle(self, path, bundle):
        data = (json.dumps(bundle, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        output = QSaveFile(path)
        if not output.open(QIODevice.WriteOnly):
            self._append(output.errorString(), "err")
            return
        if output.write(data) != len(data):
            output.cancelWriting()
            self._append(tr("Could not write the review file."), "err")
            return
        if not output.commit():
            self._append(output.errorString(), "err")

    def _on_export_audit(self):
        if self._busy:
            return
        service = self._task_service()
        result = service.export_review_audit()
        if not result.get("ok"):
            self._append(result["message"], "err")
            return
        if not result["bundle"]["payload"]["events"]:
            return
        path, _ = QFileDialog.getSaveFileName(self, tr("Export review history"),
                                             "ai-review-history.json", "JSON (*.json)")
        if not path:
            return
        if service is not self._task_service():
            self._append(tr("The document changed; export its history again."), "err")
            return
        result = service.export_review_audit()
        if not result.get("ok"):
            self._append(result["message"], "err")
            return
        self._save_json_bundle(path, result["bundle"])

    def _on_verify_audit(self):
        from core.ai_review_audit import MAX_INPUT_BYTES, verify_bundle
        path, _ = QFileDialog.getOpenFileName(self, tr("Verify review history"),
                                             "", "JSON (*.json)")
        if not path:
            return
        try:
            source = Path(path)
            if source.stat().st_size > MAX_INPUT_BYTES:
                self._append(tr("Review history file is too large."), "err")
                return
            bundle = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeError):
            self._append(tr("Could not read review history JSON."), "err")
            return
        result = verify_bundle(bundle)
        if result["ok"]:
            self._append(tr("Review history verified: {count} events. Unsigned file.",
                            count=result["event_count"]), "ok")
        else:
            self._append(result["message"], "err")

    def _refresh_project_memory(self) -> None:
        count = len(getattr(self._viewport.scene, "ai_memory", []))
        self._project_memory.setText(tr("Memory ({count})", count=count))

    def _refresh_suggestions_if_needed(self) -> None:
        scene = self._viewport.scene
        signature = (id(scene), scene.version,
                     getattr(scene, "active_layer", None),
                     getattr(getattr(scene, "edit_group", None), "uid", None))
        if signature != self._suggestion_signature:
            self._refresh_suggestions(signature=signature)

    def _refresh_suggestions(self, force: bool = False, signature=None) -> None:
        scene = self._viewport.scene
        signature = signature or (
            id(scene), scene.version, getattr(scene, "active_layer", None),
            getattr(getattr(scene, "edit_group", None), "uid", None))
        if not force and signature == self._suggestion_signature:
            return
        self._suggestion_signature = signature
        self._suggestions = ai_suggestions.suggestions(scene)
        for index, button in enumerate(self._suggestion_buttons):
            if index < len(self._suggestions):
                item = self._suggestions[index]
                button.setText(tr(item["label"]))
                button.setToolTip(item["prompt"])
                button.setVisible(True)
            else:
                button.setVisible(False)
        self._suggestion_bar.setVisible(bool(self._suggestions))

    def _apply_suggestion(self, index: int) -> None:
        if self._busy or self._pending_task_id \
                or index < 0 or index >= len(self._suggestions):
            return
        item = self._suggestions[index]
        for combo, value in (
                (self._intent_scope, item["scope"]),
                (self._intent_goal, item["goal"]),
                (self._intent_mode, item["execution"])):
            position = combo.findData(value)
            if position >= 0:
                combo.setCurrentIndex(position)
        self._input.setText(item["prompt"])
        self._input.setFocus(Qt.ShortcutFocusReason)

    def _apply_project_memory(self, facts) -> bool:
        from core.ai_memory import validate_memory
        from core.history import SetAIMemoryCommand
        try:
            clean = validate_memory(facts)
        except ValueError as exc:
            QMessageBox.warning(self, tr("Project AI memory"), str(exc))
            return False
        if clean == list(getattr(self._viewport.scene, "ai_memory", [])):
            return True
        self._viewport.history.execute(SetAIMemoryCommand(clean))
        self._refresh_project_memory()
        self._viewport.update()
        return self._viewport.history.last_error is None

    def _on_project_memory(self) -> None:
        dialog = ProjectMemoryDialog(
            getattr(self._viewport.scene, "ai_memory", []), self)
        if dialog.exec() == QDialog.Accepted:
            self._apply_project_memory(dialog.facts())

    def _task_is_read_only(self) -> bool:
        task = self._task_packet or {}
        return (task.get("execution") == "analysis_only"
                or task.get("goal") in {"check", "quantify", "explain"})

    def _stash_credentials(self, st: QSettings, slot) -> None:
        """Remember the current key/model under the provider they belong
        to (detected by prefix when the combo is on Auto). Empty fields
        never clobber a stored value."""
        key = self._key.text().strip()
        provider = (slot if slot not in (None, "auto")
                    else ai.detect_provider(key))
        if provider == "ollama":
            return
        if key:
            st.setValue(f"ia/claves/{provider}", self._key.text())
        model = self._model.currentText().strip()
        if model:
            st.setValue(f"ia/modelos/{provider}", model)

    def _on_provider_changed(self) -> None:
        """EACH provider keeps its own key and model: pasting the Gemini
        key must not erase the Groq one (user report) — running out of
        tokens on one plan and switching has to be two clicks."""
        st = self._settings()
        self._stash_credentials(st, getattr(self, "_prov_slot", None))
        cur = self._provider.currentData()
        self._prov_slot = cur
        if cur and cur != "auto":
            self._key.setText(str(st.value(f"ia/claves/{cur}", "") or ""))
            self._model.clear()      # the fetched model list is per provider
            self._model.setEditText(
                str(st.value(f"ia/modelos/{cur}", "") or ""))
        self._on_key_changed()

    def _effective_provider(self) -> str:
        chosen = self._provider.currentData()
        if chosen and chosen != "auto":
            return chosen
        return ai.detect_provider(self._key.text().strip())

    def _on_key_changed(self) -> None:
        provider = self._effective_provider()
        label, url = ai.PROVIDER_INFO[provider]
        if provider == "ollama":
            self._key_link.setText(tr(
                "Local models — install from <a href='{url}'>{url}</a>",
                url=url))
        else:
            self._key_link.setText(tr(
                "{name} — get your key at <a href='{url}'>{url}</a>",
                name=label, url=url))
        self._model.lineEdit().setPlaceholderText(
            ai.DEFAULT_MODELS[provider])
        self._ollama.setVisible(provider == "ollama")
        self._ollama_label.setVisible(provider == "ollama")

    def _config(self) -> tuple[str, str, str, str]:
        key = self._key.text().strip()
        provider = self._effective_provider()
        model = (self._model.currentText().strip()
                 or ai.DEFAULT_MODELS[provider])
        return provider, model, key, self._ollama.text().strip()

    def _review_models(self, provider):
        from core.ai_review import ROLES
        settings = self._settings()
        return {role: str(settings.value(f"ia/review_models/{provider}/{role}", "") or "")
                for role in ROLES}

    def _review_providers(self):
        from core.ai_review import ROLES
        settings = self._settings()
        return {role: str(settings.value(f"ia/review_providers/{role}", "") or "")
                for role in ROLES}

    def _review_connections(self, main_config):
        from core.ai_review import ROLES
        main_provider, main_model, main_key, ollama_url = main_config
        settings = self._settings()
        overrides = self._review_providers()
        connections = {}
        for role in ROLES:
            provider = overrides[role] or main_provider
            if provider not in ai.PROVIDERS:
                raise ValueError("Unknown specialist provider; choose a connection again.")
            model = str(settings.value(f"ia/review_models/{provider}/{role}", "") or "").strip()
            if provider == main_provider:
                key = main_key
                model = model or main_model
            else:
                key = str(settings.value(f"ia/claves/{provider}", "") or "").strip()
                model = model or str(settings.value(f"ia/modelos/{provider}", "") or "").strip()
                model = model or ai.DEFAULT_MODELS[provider]
            if provider == "ollama":
                key = ""
            if not 1 <= len(model) <= 200 or len(key) > 512:
                raise ValueError("Specialist model or connection exceeds its limit.")
            hint = self._missing_key_hint(provider, key)
            if hint is not None:
                raise ValueError(f"{role}: {hint}")
            connections[role] = {"provider": provider, "model": model,
                                 "key": key, "ollama_url": ollama_url}
        return connections

    def _on_specialist_models(self):
        if self._busy or self._pending_task_id:
            return
        provider = self._effective_provider()
        overrides = self._review_providers()
        models = {role: self._review_models(overrides[role] or provider)[role]
                  for role in overrides}
        dialog = SpecialistModelsDialog(provider, models, self,
                                        role_providers=overrides)
        if dialog.exec() == QDialog.Accepted:
            settings = self._settings()
            for role, model in dialog.models().items():
                selected_provider = dialog.providers()[role]
                settings.setValue(f"ia/review_providers/{role}", selected_provider)
                settings.setValue(f"ia/review_models/{selected_provider or provider}/{role}", model)

    def _on_modelos(self) -> None:
        if self._busy:
            return
        self._save_settings()
        provider, _model, key, ollama = self._config()
        self._append(tr("Fetching the model list from {name}…",
                        name=ai.PROVIDER_INFO[provider][0]), "muted")
        self._modelos.setEnabled(False)

        def worker() -> None:
            try:
                models = ai.list_models(provider, key, ollama)
                self._reply.emit({"modelos": True, "ok": True,
                                  "models": models})
            except Exception as exc:  # noqa: BLE001 — shown in the chat
                self._reply.emit({"modelos": True, "ok": False,
                                  "msg": str(exc)})

        threading.Thread(target=worker, daemon=True).start()

    def _missing_key_hint(self, provider: str, key: str) -> str | None:
        """The plain-words message for a hosted provider with no key, or
        None when there is nothing to say. Rafael picked «Groq (gratis)»,
        left the key empty and Test connection answered with Groq's raw
        ``HTTP 401 {"error":{"message":"Invalid API Key"…`` (Revisión 3,
        2026-09-20). A missing key is known BEFORE any network round trip,
        and the fix is one sentence, not a JSON blob."""
        if key or provider == "ollama":
            return None
        label, url = ai.PROVIDER_INFO[provider]
        return tr(
            "{name} needs an API key — the quota is free, the key is not "
            "optional. Create one at {url} (the link under the key field "
            "opens it) and paste it in the \"API key\" field — it is saved "
            "in your user profile, never in the document.", name=label,
            url=url)

    @staticmethod
    def _bad_key_hint(provider: str, err: str) -> str | None:
        """A rejected key (HTTP 401/403, or the providers' own wording),
        translated into what to check."""
        low = (err or "").lower()
        if not ("401" in low or "403" in low or "invalid api key" in low
                or "invalid_api_key" in low or "incorrect api key" in low
                or "invalid x-api-key" in low or "api key not valid" in low
                or "authentication" in low):
            return None
        label, url = ai.PROVIDER_INFO.get(provider, ("", ""))
        prefixes = {"groq": "gsk_", "anthropic": "sk-ant-", "gemini": "AIza",
                    "openrouter": "sk-or-", "openai": "sk-"}
        pre = prefixes.get(provider)
        tail = (tr(" A {name} key starts with «{prefix}».", name=label,
                   prefix=pre) if pre else "")
        return tr(
            "{name} rejected the key. Check it was pasted whole, with no "
            "spaces, and that it belongs to this provider — or create a new "
            "one at {url}.", name=label, url=url) + tail

    def _on_probar(self) -> None:
        if self._busy:
            return
        self._save_settings()
        provider, model, key, ollama = self._config()
        hint = self._missing_key_hint(provider, key)
        if hint is not None:
            self._append(hint, "err")
            return
        self._append(tr("Testing {name} ({model})…",
                        name=ai.PROVIDER_INFO[provider][0], model=model),
                     "muted")
        self._probar.setEnabled(False)

        def worker() -> None:
            ok, msg = ai.probar_conexion(provider, model, key, ollama)
            self._reply.emit({"probar": True, "ok": ok, "msg": msg})

        threading.Thread(target=worker, daemon=True).start()

    # ---- Photo attachment ---------------------------------------------------
    #: Longest edge a photo is scaled down to before upload. Enough detail
    #: to read shapes; the convo is resent EVERY turn, so size compounds.
    FOTO_MAX_EDGE = 1280

    def _on_foto(self) -> None:
        path, _f = file_dialogs.getOpenFileName(
            self, tr("Attach a photo"), "",
            tr("Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp)"
               ";;All files (*)"))
        if path:
            self._attach_photo(path)

    def _attach_photo(self, path: str) -> None:
        encoded = self._encode_photo(path)
        if encoded is None:
            self._append(tr("Could not read the image."), "err")
            return
        # Qt returns native separators: ``\`` on Windows and ``/`` on Unix.
        # Keep paths out of the chip and the message sent to the model.
        name = path.replace("\\", "/").rsplit("/", 1)[-1]
        self._foto = (*encoded, name)
        self._foto_chip.setText("📷 " + name)
        self._foto_chip.setVisible(True)
        self._foto_quitar.setVisible(True)
        self._append(tr(
            "Photo attached: {name} — it goes with your next message. "
            "Include the real measurements: a photo has none.", name=name),
            "muted")

    def _encode_photo(self, path: str) -> tuple[str, str] | None:
        """(base64, mime) of the photo, EXIF-rotated and scaled down to
        FOTO_MAX_EDGE, re-encoded as JPEG (a photo as PNG is ~10× the
        bytes, and the payload rides on every later turn)."""
        reader = QImageReader(path)
        reader.setAutoTransform(True)      # phone photos carry EXIF rotation
        image = reader.read()
        if image.isNull():
            return None
        if max(image.width(), image.height()) > self.FOTO_MAX_EDGE:
            if image.width() >= image.height():
                image = image.scaledToWidth(
                    self.FOTO_MAX_EDGE, Qt.SmoothTransformation)
            else:
                image = image.scaledToHeight(
                    self.FOTO_MAX_EDGE, Qt.SmoothTransformation)
        buf = QBuffer()
        buf.open(QIODevice.WriteOnly)
        image.save(buf, "JPEG", 85)
        return base64.b64encode(bytes(buf.data())).decode(), "image/jpeg"

    def _clear_foto(self) -> None:
        self._foto = None
        self._foto_chip.setVisible(False)
        self._foto_quitar.setVisible(False)

    # ---- Chat loop ----------------------------------------------------------
    def _on_send(self) -> None:
        if self._busy or self._pending_task_id:
            return
        prompt = self._input.text().strip()
        if not prompt:
            return
        main_config = self._config()
        provider, _model, key, _ollama = main_config
        if self._specialist_review.isChecked():
            try:
                self._review_role_connections = self._review_connections(main_config)
            except ValueError as exc:
                self._append(str(exc), "err")  # leave prompt intact
                return
        else:
            hint = self._missing_key_hint(provider, key)
            if hint is not None:
                self._append(hint, "err")
                return
        task = self._create_task(prompt)
        if not task.get("ok"):
            self._append(tr("Could not create the AI task: {err}",
                            err=task.get("message") or task), "err")
            return
        self._task_packet = task
        self._active_task_id = task["task_id"]
        self._task_changed = False
        self._analysis_nudged = False
        self._python_nudged = False
        self._clear_typed_preview()
        self._task_service().transition(self._active_task_id, "running")
        self._task_chip.setText(tr(
            "Task: {goal} · {scope} · {count} entities · {mode}",
            goal=task["goal"], scope=task["scope"]["kind"],
            count=task["scope"]["entity_count"], mode=task["execution"]))
        self._task_chip.setVisible(True)
        self._set_task_controls_enabled(False)
        self._input.clear()
        self._save_settings()
        self._append(f"Tú: {prompt}", "user")
        message: dict = {"role": "user", "text": prompt}
        if self._foto is not None:
            b64, mime, name = self._foto
            message["image_b64"] = b64
            message["image_mime"] = mime
            self._append(f"[📷 {name}]", "user")
            provider, model = self._config()[:2]
            if not ai.supports_vision(provider, model):
                self._append(tr(
                    "Heads-up: {model} has no vision, so the photo will "
                    "NOT be sent — it is kept, and flows again when you "
                    "switch to a vision model (Anthropic, OpenAI, Gemini, "
                    "OpenRouter).", model=model), "muted")
            self._clear_foto()
        self._convo.append(message)
        self._round = 0
        self._nudged = False
        self._last_prompt = prompt
        if self._specialist_review.isChecked():
            self._start_specialist_review()
            return
        self._next_turn()

    def _start_specialist_review(self):
        from core import ai_review
        try:
            packet = ai_review.snapshot(self._viewport.scene, self._task_packet)
        except ValueError as exc:
            self._append(str(exc), "err")
            self._task_service().transition(self._active_task_id, "failed")
            self._finish()
            return
        self._busy = True
        self._send.setEnabled(False)
        self._cancel.setVisible(True)
        self._cancel.setEnabled(True)
        self._generation += 1
        generation = self._generation
        self._review_scene = self._viewport.scene
        token = ai_review.ReviewCancellation()
        self._cancel_token = token
        config = self._config()
        role_connections = {role: dict(connection) for role, connection in
                            self._review_role_connections.items()}
        self._append(tr("Two specialists are reviewing the same metadata snapshot. Photos and geometry are not included."), "muted")

        def worker():
            try:
                report = ai_review.run_review(packet, *config, token,
                                              role_connections=role_connections)
                self._reply.emit({"review": report, "generation": generation})
            except ai.CancelledError:
                pass
            except Exception as exc:
                self._reply.emit({"review_error": str(exc), "generation": generation})
        threading.Thread(target=worker, daemon=True).start()

    def _next_turn(self) -> None:
        self._busy = True
        self._send.setEnabled(False)
        self._cancel.setVisible(True)
        self._cancel.setEnabled(True)
        self._stream_text = ""
        self._stream_preview.clear()
        self._stream_preview.setVisible(True)
        self._append(tr("thinking…"), "muted")
        provider, model, key, ollama = self._config()
        convo = ai.compact_messages(ai.slim_messages(
            self._convo, vision=ai.supports_vision(provider, model)))
        # Ground a short request in the document the user can see.  This is
        # deliberately bounded; an MCP client that needs the whole outline
        # can page through get_document_context instead.
        context = ai_context.assistant_context(self._viewport.scene)
        system = (SYSTEM_PROMPT + "\n\nContexto actual del documento (solo "
                  "lectura; puede estar truncado):\n" + context)
        if self._task_packet is not None:
            task_context = {key: self._task_packet[key] for key in (
                "task_id", "intent", "goal", "execution", "base_revision",
                "scope", "constraints", "assumptions",
                "project_memory", "acceptance_criteria", "plan")}
            task_context["read_only"] = self._task_is_read_only()
            task_context["raw_python_allowed"] = self._allow_python.isChecked()
            system += ("\n\nContrato de tarea fijado por la interfaz. Respeta "
                       "estrictamente el alcance y los supuestos; no amplíes "
                       "los entity_ids. Si read_only es true, NO cambies el "
                       "documento. Si raw_python_allowed es false, NO incluyas "
                       "Python: usa acciones JSON tipadas o explica la limitación:\n"
                       + json.dumps(task_context, ensure_ascii=False,
                                    separators=(",", ":")))

        budget = TOKENS_BY_PROVIDER.get(provider, MAX_TOKENS)
        self._generation += 1
        generation = self._generation
        token = ai.CancellationToken()
        self._cancel_token = token

        def on_retry(n, total, wait, reason) -> None:
            # A busy provider (Gemini's 503 «high demand»): say so and
            # wait, instead of ending the recipe at the walls.
            self._reply.emit({"retry": True, "generation": generation,
                              "n": n, "total": total,
                              "wait": wait, "reason": reason})

        def on_chunk(text: str) -> None:
            self._reply.emit({"stream": True, "generation": generation,
                              "text": text})

        def worker() -> None:
            try:
                text = ai.chat(provider, model, key, system, convo,
                               ollama_url=ollama, max_tokens=budget,
                               on_retry=on_retry, on_chunk=on_chunk,
                               cancel_token=token, stream=True)
                self._reply.emit({"ok": True, "generation": generation,
                                  "text": text})
            except ai.CancelledError:
                self._reply.emit({"cancelled": True,
                                  "generation": generation})
            except Exception as exc:  # noqa: BLE001 — shown in the chat
                self._reply.emit({"ok": False, "generation": generation,
                                  "error": str(exc)})

        threading.Thread(target=worker, daemon=True).start()

    @staticmethod
    def _preview_text(result: dict) -> str:
        lines = [tr("Review these changes before applying:")]
        for change in result.get("changes", []):
            name = change.get("entity_name") or change.get("entity_id")
            lines.append("• {name} · {field}: {before} → {after}".format(
                name=name, field=change.get("field"),
                before=change.get("before"), after=change.get("after")))
        if not result.get("changes"):
            lines.append(tr("No effective changes."))
        return "\n".join(lines)

    def _clear_typed_preview(self) -> None:
        self._pending_task_id = ""
        self._pending_idempotency_key = ""
        if hasattr(self, "_change_preview"):
            self._change_preview.clear()
            self._change_preview.setVisible(False)
            self._preview_buttons.setVisible(False)
            self._apply_changes.setEnabled(True)
            self._discard_changes.setEnabled(True)

    def _typed_failure(self, result) -> None:
        message = (result.get("message") if isinstance(result, dict)
                   else str(result))
        self._append(tr("Typed change proposal was rejected: {err}",
                        err=message), "err")
        if self._active_task_id:
            service = self._change_service()
            summary = service.summary()
            if summary and summary.get("task_id") == self._active_task_id:
                service.discard(self._active_task_id)
        self._clear_typed_preview()
        self._finish()

    def _prepare_typed_preview(self, actions: list[dict]) -> None:
        task = self._task_packet or {}
        task_id = self._active_task_id
        key = f"{task_id}-assistant-{self._round + 1}"
        service = self._change_service()
        result = service.propose(
            task_id=task_id, intent=task.get("intent", ""),
            base_revision=task.get("base_revision"),
            idempotency_key=key, actions=actions)
        if not result.get("ok"):
            self._typed_failure(result)
            return
        validation = service.validate(task_id)
        if not validation.get("ok") or not validation.get(
                "validation", {}).get("valid"):
            self._typed_failure(validation)
            return
        result = service.request_commit(
            task_id=task_id, base_revision=task.get("base_revision"),
            idempotency_key=key)
        if not result.get("ok"):
            self._typed_failure(result)
            return
        self._pending_task_id = task_id
        self._pending_idempotency_key = key
        self._change_preview.setPlainText(self._preview_text(result))
        self._change_preview.setVisible(True)
        self._preview_buttons.setVisible(True)
        self._busy = False
        self._send.setEnabled(False)
        self._append(tr(
            "The proposal is validated. Review it, then Apply or Discard."),
            "muted")

    def _on_apply_typed_changes(self) -> None:
        task_id = self._pending_task_id
        if not task_id:
            return
        self._apply_changes.setEnabled(False)
        self._discard_changes.setEnabled(False)
        result = self._change_service().approve(task_id)
        if not result.get("ok"):
            self._typed_failure(result)
            return
        self._task_changed = bool(result.get("changed"))
        if self._task_changed:
            self._append(tr("Applied {n} validated changes as one undo step.",
                            n=len(result.get("changes", []))), "ok")
        else:
            self._append(tr("The validated proposal required no changes."),
                         "muted")
        self._clear_typed_preview()
        self._viewport.notify_scene_changed()
        self._finish()

    def _on_discard_typed_changes(self) -> None:
        task_id = self._pending_task_id
        if not task_id:
            return
        result = self._change_service().discard(task_id)
        if not result.get("ok"):
            self._typed_failure(result)
            return
        self._append(tr("Discarded the proposal; the model is unchanged."),
                     "muted")
        self._clear_typed_preview()
        self._finish()

    def _on_reply(self, msg: dict) -> None:
        generation = msg.get("generation")
        if generation is not None and generation != self._generation:
            return
        if "review_error" in msg:
            self._append(msg["review_error"], "err")
            self._task_service().transition(self._active_task_id, "failed")
            self._finish()
            return
        if "review" in msg:
            from core.ai_review import report_text
            report = msg["review"]
            if (self._review_scene is not self._viewport.scene or
                    report["base_revision"] != self._viewport.scene.content_version):
                report.update(status="stale", specialists=[], conflicts=[])
                self._append(tr("The document changed during review. Run the review again."), "err")
            else:
                self._append(report_text(report), "ai")
            self._task_service().record_review(self._active_task_id, report)
            self._finish()
            return
        if msg.get("stream"):
            self._stream_text += str(msg.get("text", ""))
            if not self._stream_flush_scheduled:
                self._stream_flush_scheduled = True
                # Providers often emit token-sized chunks. Coalesce all
                # queued chunks for this event-loop turn instead of replacing
                # the whole preview document once per token.
                QTimer.singleShot(0, self._flush_stream_preview)
            return
        if msg.get("cancelled"):
            return
        if msg.get("retry"):
            reason = str(msg.get("reason", ""))
            short = reason.split(":", 1)[0]
            self._append(tr(
                "The provider is busy ({why}) — retry {n} of {total} in {wait} s…",
                why=short, n=msg.get("n"), total=msg.get("total"),
                wait=int(msg.get("wait", 0))), "muted")
            return
        if msg.get("modelos"):
            self._modelos.setEnabled(True)
            if msg.get("ok"):
                models = msg.get("models") or []
                current = self._model.currentText()
                self._model.clear()
                self._model.addItems(models)
                self._model.setEditText(current)
                self._append(tr(
                    "{n} models available to your key — pick one from "
                    "the list.", n=len(models)), "ok")
                self._model.showPopup()
            else:
                self._append(tr("Could not list models: {err}",
                                err=msg.get("msg")), "err")
            return
        if msg.get("probar"):
            self._probar.setEnabled(True)
            if msg.get("ok"):
                self._append(tr("Connection OK — the model answered."),
                             "ok")
            else:
                self._append(tr("Connection failed: {err}",
                                err=msg.get("msg")), "err")
                bad = self._bad_key_hint(self._effective_provider(),
                                         str(msg.get("msg")))
                if bad is not None:
                    self._append(bad, "err")
                if "model_not_found" in str(msg.get("msg")):
                    self._append(tr(
                        'That model no longer exists for your key — press '
                        '"Models" to list the available ones.'), "err")
            return
        self._cancel_token = None
        self._cancel.setVisible(False)
        self._stream_preview.setVisible(False)
        if not msg.get("ok"):
            self._append(tr("Error: {err}", err=msg.get("error")), "err")
            self._finish()
            return
        text = ai.strip_thoughts(msg["text"])
        self._convo.append({"role": "assistant", "text": text})
        self._append(f"IA: {text}", "ai")
        code = ai.extract_code(text)
        try:
            actions = ai.extract_typed_actions(text)
        except ValueError as exc:
            self._typed_failure(str(exc))
            return
        if actions is not None:
            if code is not None:
                self._typed_failure(
                    "a reply cannot mix typed JSON actions and Python")
                return
            self._prepare_typed_preview(actions)
            return
        attempted_python = code is not None or ai.truncated_code(text)
        if attempted_python and self._task_is_read_only():
            if not self._analysis_nudged:
                self._analysis_nudged = True
                self._append(tr(
                    "Analysis-only mode blocked the returned recipe; asking for a read-only answer."),
                    "muted")
                self._convo.append({"role": "user", "text":
                    "La tarea es analysis_only. El bloque Python fue "
                    "rechazado y NO se ejecutó. Responde con análisis y "
                    "recomendaciones, sin código ni cambios al documento."})
                self._next_turn()
                return
            self._append(tr(
                "Analysis-only mode blocked a second recipe; the document is unchanged."),
                "err")
            self._finish()
            return
        if attempted_python and not self._allow_python.isChecked():
            if not self._python_nudged:
                self._python_nudged = True
                self._append(tr(
                    "Advanced Python is off; asking for typed actions instead."),
                    "muted")
                self._convo.append({"role": "user", "text":
                    "Python avanzado está desactivado para esta sesión y el "
                    "bloque NO se ejecutó. Usa un bloque ```json con acciones "
                    "tipadas (incluyendo create_box/create_cylinder cuando "
                    "sirvan). Si la operación no está soportada, explica la "
                    "limitación sin afirmar que cambiaste el modelo."})
                self._next_turn()
                return
            self._append(tr(
                "Advanced Python blocked a second recipe; the document is unchanged."),
                "err")
            self._finish()
            return
        if code is None and ai.truncated_code(text):
            # Cut by max_tokens mid-recipe: half a block must neither run
            # nor end the loop silently — ask for a smaller, complete one.
            if self._round < MAX_ROUNDS:
                self._round += 1
                self._append(tr("The reply was cut off mid-code — asking "
                                "for a shorter, complete block."), "muted")
                self._convo.append({"role": "user", "text":
                    "Tu respuesta se cortó a mitad del bloque ```python "
                    "(límite de tokens). NO continúes donde quedaste: "
                    "reenvía UN bloque completo y más corto, avanzando "
                    "solo la primera parte del trabajo; el resto irá en "
                    "turnos siguientes."})
                self._next_turn()
                return
            self._append(tr('The reply was cut off and the step limit is '
                            'used up — type "continue" to keep going.'),
                         "err")
            self._finish()
            return
        if code is not None and self._round >= MAX_ROUNDS:
            # A recipe arrived but the budget for ONE request is spent:
            # never swallow it silently — the convo survives, so any new
            # message (e.g. "continúa") picks up exactly here.
            self._append(tr('Step limit reached for one request '
                            '({n}) — type "continue" to keep going.',
                            n=MAX_ROUNDS), "muted")
            self._finish()
            return
        if code is None:
            if self._round == 0 and not self._nudged and _asks_to_build(
                    self._last_prompt) and "?" not in text[-80:] \
                    and not self._task_is_read_only():
                # A model that narrates a build it never sent (Groq's
                # compound answered «se añadió una cumbrera…» with no
                # block, Marco 2026-09-15): one push, then let it be.
                self._nudged = True
                self._append(tr("No executable action came back — asking for a typed proposal or recipe."),
                             "muted")
                self._convo.append({"role": "user", "text":
                    "No incluiste un bloque ejecutable: NADA se ejecutó y el "
                    "modelo no cambió. Para propiedades de entidades existentes, "
                    "envía UN bloque ```json con {\"actions\":[...]}, usando "
                    "create_box/create_cylinder cuando corresponda. Python solo "
                    "está permitido si raw_python_allowed es true."})
                self._next_turn()
                return
            self._finish()
            return
        self._round += 1
        result = ai.run_transactional(self._viewport, code, self._scope)
        self._task_changed = self._task_changed or bool(result["changed"])
        summary = []
        if result["stdout"]:
            out = result["stdout"].rstrip()
            if len(out) > 1500:      # a print-happy recipe rides EVERY turn
                out = out[:700] + "\n… (recortado) …\n" + out[-700:]
            summary.append(out)
        if result["error"]:
            summary.append("ERROR (todo revertido): " + str(result["error"]))
            if result["stderr"]:
                summary.append(result["stderr"].rstrip()[-800:])
        summary.append(f"(cambió el modelo: {result['changed']})")
        feedback = "Resultado de la ejecución:\n" + "\n".join(summary)
        self._append(feedback, "muted")
        provider, model = self._config()[:2]
        shot = None
        # Only shoot when the model CHANGED: after an error or an
        # inspect-only block the previous screenshot is still accurate
        # (slim_messages keeps the latest one in the convo).
        if (self._shots.isChecked() and result["changed"]
                and ai.supports_vision(provider, model)):
            shot = self._screenshot_b64()
        self._convo.append({"role": "user", "text": feedback,
                            **({"image_png_b64": shot} if shot else {})})
        self._next_turn()

    def _flush_stream_preview(self) -> None:
        self._stream_flush_scheduled = False
        if not self._busy or self._stream_preview.isHidden():
            return
        self._stream_preview.setPlainText(self._stream_text)
        bar = self._stream_preview.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _on_cancel(self) -> None:
        """Stop generation and invalidate every queued event from that turn."""
        if not self._busy:
            return
        token = self._cancel_token
        self._cancel_token = None
        self._generation += 1
        if token is not None:
            token.cancel()
        self._stream_preview.setVisible(False)
        self._stream_text = ""
        self._stream_flush_scheduled = False
        if self._active_task_id:
            service = self._change_service()
            summary = service.summary()
            if summary and summary.get("task_id") == self._active_task_id:
                service.discard(self._active_task_id)
            self._task_service().transition(
                self._active_task_id, "cancelled",
                {"changed": self._task_changed, "code": "cancelled",
                 "message": "cancelled by user",
                 "content_revision": self._viewport.scene.content_version})
        if self._task_changed:
            self._append(tr(
                "Cancelled. Partial AI output was not executed; changes from earlier completed steps remain undoable."),
                "muted")
        else:
            self._append(tr(
                "Cancelled. Partial AI output was not executed and the model is unchanged."),
                "muted")
        self._finish()

    def _finish(self) -> None:
        self._busy = False
        self._cancel_token = None
        self._review_role_connections = {}
        self._cancel.setVisible(False)
        self._stream_preview.setVisible(False)
        pending = bool(self._pending_task_id)
        self._send.setEnabled(not pending)
        self._set_task_controls_enabled(not pending)
        if self._active_task_id:
            current = self._task_service().get(self._active_task_id)
            terminal = {"committed", "completed", "discarded", "stale",
                        "cancelled", "partial", "failed"}
            if current.get("status") not in terminal and not pending:
                status = "committed" if self._task_changed else "completed"
                self._task_service().transition(
                    self._active_task_id, status,
                    {"changed": self._task_changed,
                     "content_revision": self._viewport.scene.content_version})

        self._refresh_review_export()

    def _screenshot_b64(self) -> str | None:
        try:
            # 640 px JPEG: the model reads a screenshot fine at that size
            # and it costs a quarter of the 768 px PNG it used to be —
            # the screenshot is the fattest thing in every turn.
            image = self._viewport.render_image(640, 427)
            buf = QBuffer()
            buf.open(QIODevice.WriteOnly)
            image.save(buf, "JPEG", 72)
            return base64.b64encode(bytes(buf.data())).decode()
        except Exception:  # noqa: BLE001 — vision is best-effort
            return None


def _esc(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


#: The tests and older code name it by its dialog-era name.
AsistenteDialog = AsistentePanel


def setup(app) -> None:
    """The «AI» tab of the side tray (shared with the MCP bridge) and
    Extensions ▸ AI Assistant (Ctrl+Shift+A), which brings the tab
    forward — shown again if it was hidden — with the cursor in the input."""
    panel = AsistentePanel(app.viewport)
    dock = app.add_panel(tr("AI"), panel, panel="ai", stretch=1)
    app.window._ai_assistant = panel

    def summon() -> None:
        app.show_panel(dock)
        panel.focus_input()

    app.add_menu_action(tr("AI Assistant"), summon, "Ctrl+Shift+A", tr(
        "Open a chat with an AI that can read and change the model."))
