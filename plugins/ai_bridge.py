# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""AI Bridge plugin — let an AI coding agent drive the live document (MCP).

The realisation of invariant #5 (AI-native): the agent generates RECIPES of
actions over the deterministic engine, never raw meshes. The «AI» tab of
the side tray (section "AI bridge (MCP)", or Extensions ▸ AI Bridge (MCP))
starts a localhost-only TCP server; the companion
``scripts/ingetrazo_mcp.py`` bridges it to Claude Code / Claude Desktop as
an MCP server. The usual pattern for app MCP bridges (a TCP server inside
the app + an MCP process outside), with three legs up:

- ``run_python`` executes through the Python Console's transactional
  machinery: every AI action is ONE undo step, and a script that raises is
  rolled back whole — the agent can never leave the document half-mutated.
- ``screenshot`` renders the real viewport (``render_image``), closing the
  "the agent can't see what it built" gap: describe → build → LOOK → fix.
- The hermeticity guard stays in the loop: recipes that would commit a
  broken solid are refused by the engine itself.

Protocol (framed for the bridge, not for humans): newline-delimited JSON on
127.0.0.1:4763 (``INGETRAZO_AI_PORT`` overrides). Request
``{"id": n, "auth": token, "tool": name, "args": {...}}`` → reply
``{"id": n, "ok": bool, "result": ... | "error": str}``. The companion MCP
process reads the rotating token from an owner-readable session file; it is
never printed in setup commands. Messages are bounded to 1 MiB and legacy
write tools are off until the user enables them for that bridge session. One
client at a time; everything the tools touch runs on the Qt MAIN thread
(queued-signal relay to a bound method — the documented PySide6 gotcha).
"""
from __future__ import annotations

import hmac
import json
import os
import secrets
import socket
import sys
import tempfile
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QHBoxLayout, QLabel, QPlainTextEdit,
                               QPushButton, QVBoxLayout, QWidget)

from core.i18n import tr
from views.fold_section import FoldSection, narrow

DEFAULT_PORT = 4763
MAX_MESSAGE_BYTES = 1024 * 1024


class _Bridge(QObject):
    """The in-app half: accepts one agent connection and executes its tool
    calls on the Qt main thread."""

    # Signal(object), NOT Signal(dict): a dict payload on a queued
    # connection may be marshalled into a QVariantMap — the slot then gets a
    # COPY, sets the copied Event, and the worker times out forever. object
    # passes the PyObject by reference. (Cost us a hunt; now documented.)
    _dispatch = Signal(object)
    activity_changed = Signal(object)

    def __init__(self, viewport) -> None:
        super().__init__(viewport)
        self._viewport = viewport
        self._server: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._scope: dict = {"__name__": "__ai__"}
        self.port: int | None = None
        self.session_token = ""
        self.allow_legacy_writes = False
        self.client_connected = False
        self.client_name = ""
        self.request_count = 0
        self.last_tool = ""
        self.last_error = ""
        # Queued to a BOUND method of this main-thread QObject — connecting a
        # lambda would run the slot on the worker thread (CLAUDE.md gotcha).
        self._dispatch.connect(self._run_on_main, Qt.QueuedConnection)

    # ---- Lifecycle ----------------------------------------------------------
    def start(self) -> int:
        port = int(os.environ.get("INGETRAZO_AI_PORT", DEFAULT_PORT))
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", port))
        srv.listen(1)
        srv.settimeout(0.5)
        self._server = srv
        self.port = srv.getsockname()[1]
        self.allow_legacy_writes = False
        self.client_connected = False
        self.client_name = ""
        self.request_count = 0
        self.last_tool = ""
        self.last_error = ""
        self.session_token = secrets.token_urlsafe(32)
        try:
            from core.ai_bridge_auth import write_credential
            write_credential(self.session_token, self.port)
        except Exception:
            srv.close()
            self._server = None
            self.port = None
            self.session_token = ""
            raise
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._serve, name="ingetrazo-ai-bridge", daemon=True)
        self._thread.start()
        return self.port

    def stop(self) -> None:
        self._stop.set()
        if self._server is not None:
            try:
                self._server.close()
            except OSError:
                pass
            self._server = None
        if self.session_token:
            from core.ai_bridge_auth import remove_credential
            remove_credential(self.session_token)
        self.allow_legacy_writes = False
        self.port = None
        self.session_token = ""
        self.client_connected = False
        self.client_name = ""
        self.activity_changed.emit(self.activity())

    @property
    def running(self) -> bool:
        return self._server is not None

    def activity(self) -> dict:
        return {"connected": self.client_connected,
                "client_name": self.client_name,
                "request_count": self.request_count,
                "last_tool": self.last_tool,
                "last_error": self.last_error,
                "legacy_writes": self.allow_legacy_writes}

    @staticmethod
    def _wire_error(message: str, req_id=None) -> bytes:
        return (json.dumps({"id": req_id, "ok": False, "error": message})
                + "\n").encode()

    # ---- Worker side ---------------------------------------------------------
    def _serve(self) -> None:
        srv = self._server
        while not self._stop.is_set() and srv is not None:
            try:
                conn, _addr = srv.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            with conn:
                self.client_connected = True
                self.activity_changed.emit(self.activity())
                conn.settimeout(0.5)
                buf = b""
                while not self._stop.is_set():
                    try:
                        chunk = conn.recv(65536)
                    except socket.timeout:
                        continue
                    except OSError:
                        break
                    if not chunk:
                        break
                    buf += chunk
                    if len(buf) > MAX_MESSAGE_BYTES and b"\n" not in buf:
                        try:
                            conn.sendall(self._wire_error(
                                "request exceeds 1 MiB limit"))
                        except OSError:
                            pass
                        break
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        if not line.strip():
                            continue
                        if len(line) > MAX_MESSAGE_BYTES:
                            reply = self._wire_error(
                                "request exceeds 1 MiB limit")
                        else:
                            reply = self._handle_line(line)
                        try:
                            conn.sendall(reply)
                        except OSError:
                            break
                self.client_connected = False
                self.activity_changed.emit(self.activity())

    def _handle_line(self, line: bytes) -> bytes:
        if len(line) > MAX_MESSAGE_BYTES:
            return self._wire_error("request exceeds 1 MiB limit")
        try:
            req = json.loads(line)
        except ValueError:
            return self._wire_error("bad json")
        if not isinstance(req, dict):
            return self._wire_error("request must be an object")
        if not hmac.compare_digest(str(req.get("auth", "")),
                                   self.session_token):
            return self._wire_error("unauthorized", req.get("id"))
        if not isinstance(req.get("args") or {}, dict):
            return self._wire_error("args must be an object", req.get("id"))
        job = {"req": req, "done": threading.Event(), "reply": None}
        self._dispatch.emit(job)
        job["done"].wait(timeout=120.0)
        reply = job["reply"] or {"id": req.get("id"), "ok": False,
                                 "error": "timed out on the UI thread"}
        return (json.dumps(reply) + "\n").encode()

    # ---- Main-thread side ----------------------------------------------------
    def _run_on_main(self, job: dict) -> None:
        req = job["req"]
        tool = req.get("tool", "")
        args = req.get("args") or {}
        self.request_count += 1
        self.client_name = str(req.get("client", "MCP client"))[:120]
        self.last_tool = str(tool)
        self.last_error = ""
        try:
            handler = getattr(self, f"_tool_{tool}", None)
            if handler is None:
                raise ValueError(f"unknown tool {tool!r}")
            result = handler(**args)
            job["reply"] = {"id": req.get("id"), "ok": True, "result": result}
        except Exception as exc:  # noqa: BLE001 — reported to the agent
            self.last_error = f"{type(exc).__name__}: {exc}"
            job["reply"] = {"id": req.get("id"), "ok": False,
                            "error": self.last_error}
        finally:
            self.activity_changed.emit(self.activity())
            job["done"].set()

    # ---- Tools ---------------------------------------------------------------
    def _tool_run_python(self, code: str = "") -> dict:
        """Execute ``code`` via the shared transactional executor (core.ai):
        one undoable step, whole-rollback on error, no undo entry when
        nothing changed."""
        if not self.allow_legacy_writes:
            raise PermissionError(
                "run_python is disabled; enable legacy write tools in the "
                "AI bridge panel for this session")
        from core.ai import run_transactional
        return run_transactional(self._viewport, code, self._scope)

    def _tool_query_model(self) -> dict:
        vp = self._viewport
        scene = vp.scene
        lo, hi = scene.bounds()
        insts = sum(1 for g in scene.groups
                    if getattr(g, "xform", None) is not None)
        return {
            "faces": len(scene.mesh.faces),
            "edges": len(scene.mesh.edges),
            "groups": len(scene.groups) - insts,
            "component_instances": insts,
            "group_names": [g.name for g in scene.groups][:100],
            "materials": sorted(getattr(scene, "materials", {}) or {})[:100],
            "layers": [ly.name for ly in scene.layers],
            "dimensions": len(getattr(scene, "dimensions", []) or []),
            "section_planes": len(getattr(scene, "section_planes", []) or []),
            "selection": len(scene.selection),
            "bounds": (None if lo is None else
                       {"min": [lo.x(), lo.y(), lo.z()],
                        "max": [hi.x(), hi.y(), hi.z()]}),
        }

    def _tool_get_document_context(self, limit: int = 50,
                                   cursor: str | None = None) -> dict:
        """Bounded document context for an agent's first read of a model."""
        from core.ai_context import document_context
        return document_context(self._viewport.scene, limit, cursor)

    def _tool_find_entities(self, query: str = "", limit: int = 50,
                            cursor: str | None = None) -> dict:
        """Resolve a group/component by name, UID, or tag."""
        from core.ai_context import find_entities
        return find_entities(self._viewport.scene, query, limit, cursor)

    def _tool_get_entities(self, entity_ids: list | None = None) -> dict:
        """Detailed records for stable group/component identifiers."""
        from core.ai_context import get_entities
        return get_entities(self._viewport.scene, entity_ids or [])

    def _tool_get_capabilities(self) -> dict:
        """The read/write capabilities currently available through MCP."""
        from core.ai_context import capabilities
        result = capabilities()
        result["security"] = {
            "authenticated_session": True,
            "max_message_bytes": MAX_MESSAGE_BYTES,
            "legacy_write_tools_enabled": self.allow_legacy_writes,
        }
        return result

    def _tool_screenshot(self, width: int = 1024, height: int = 768) -> dict:
        width = max(64, min(int(width), 4096))
        height = max(64, min(int(height), 4096))
        image = self._viewport.render_image(width, height)
        out_dir = Path(tempfile.gettempdir()) / "ingetrazo-ai"
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / "viewport.png"
        image.save(str(out))
        return {"path": str(out), "width": width, "height": height}

    def _tool_undo(self) -> dict:
        if not self.allow_legacy_writes:
            raise PermissionError("undo is disabled with legacy write tools")
        ok = self._viewport.history.undo()
        self._viewport.update()
        return {"ok": bool(ok)}

    def _tool_redo(self) -> dict:
        if not self.allow_legacy_writes:
            raise PermissionError("redo is disabled with legacy write tools")
        ok = self._viewport.history.redo()
        self._viewport.update()
        return {"ok": bool(ok)}


def mcp_command(platform: str | None = None, frozen: bool | None = None,
                executable: str | None = None, root: Path | None = None,
                env: dict | None = None) -> list[str]:
    """The command an MCP client must run to reach this IngeTrazo — the
    packaged app carries the server, so nobody needs Python installed:
    ``ingetrazo-mcp.exe`` beside the app on Windows, ``<ingetrazo> --mcp``
    for the Linux/macOS packages, and the script itself from a checkout.

    The Linux packages need the command that is valid FROM THE HOST and
    OUTLIVES this run, not ``sys.executable``: an AppImage mounts itself
    under a fresh ``/tmp/.mount_*`` each launch (the path the dialog used
    to print died with the session), a Flatpak's executable lives inside
    the sandbox (``flatpak run <id> --mcp`` is the door), and a snap is
    reached through ``/snap/bin``. Marco found the gap setting Antigravity
    up for the tutorial (2026-09-21)."""
    from pathlib import PurePosixPath, PureWindowsPath
    platform = platform or sys.platform
    frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    executable = executable or sys.executable
    env = os.environ if env is None else env
    windows = platform.startswith("win")
    PathOf = PureWindowsPath if windows else PurePosixPath   # host-agnostic
    if not windows:
        if env.get("APPIMAGE"):
            return [env["APPIMAGE"], "--mcp"]
        if env.get("FLATPAK_ID"):
            return ["flatpak", "run", env["FLATPAK_ID"], "--mcp"]
        if env.get("SNAP_NAME"):
            return [f"/snap/bin/{env['SNAP_NAME']}", "--mcp"]
    if frozen:
        exe = PathOf(executable)
        if windows:
            return [str(exe.with_name("ingetrazo-mcp.exe"))]
        return [str(exe), "--mcp"]
    root_text = str(root or Path(__file__).resolve().parents[1])
    # Tests and cross-platform launchers may hand a host ``Path`` to a
    # target-platform command.  A Windows ``Path('/src/app')`` stringifies
    # with backslashes, which PurePosixPath treats as literal characters.
    if not windows:
        root_text = root_text.replace("\\", "/")
    root = PathOf(root_text)
    python = "python" if windows else "python3"
    return [python, str(root / "scripts" / "ingetrazo_mcp.py")]


def desktop_config_path(platform: str | None = None) -> str:
    """Where Claude Desktop reads its MCP servers on this platform."""
    platform = platform or sys.platform
    if platform.startswith("win"):
        return r"%APPDATA%\\Claude\\claude_desktop_config.json"
    if platform == "darwin":
        return "~/Library/Application Support/Claude/claude_desktop_config.json"
    return "~/.config/Claude/claude_desktop_config.json"


#: Where the common MCP clients read a ``mcpServers`` block like the one the
#: dialog prints (the same JSON, or the equivalent, works in every one:
#: MCP is an open standard, not a Claude feature).
OTHER_CLIENTS = (
    ("Cursor", "~/.cursor/mcp.json"),
    ("VS Code (Copilot)", ".vscode/mcp.json  (key \"servers\")"),
    ("Windsurf", "~/.codeium/windsurf/mcp_config.json"),
    # Google retired Gemini CLI's free Google-account login on 2026-06-18;
    # its successor for individuals is Antigravity CLI (`agy`), which reads
    # this file (Marco hit the shutdown notice on 2026-09-21).
    ("Antigravity CLI (Google)", "~/.gemini/config/mcp_config.json"),
    ("Codex CLI", "~/.codex/config.toml  ([mcp_servers.ingetrazo])"),
)


def connect_instructions(port: int, platform: str | None = None, **kw) -> str:
    """Copy-and-paste text for the dialog the Extensions entry shows once
    the bridge is up: Claude Code's one-liner, the JSON every other MCP
    client takes, and where each of them reads it."""
    cmd = mcp_command(platform, **kw)
    quoted = " ".join(f'"{c}"' if " " in c else c for c in cmd)
    config = {"mcpServers": {"ingetrazo": {"command": cmd[0], "args": cmd[1:]}}}
    others = "\n".join(f"    {name}: {path}" for name, path in OTHER_CLIENTS)
    return (
        tr("The AI bridge is listening on 127.0.0.1:{port}. Connect ANY MCP "
           "client — MCP is an open standard: Claude Code, Claude Desktop, "
           "Cursor, VS Code, Windsurf, Antigravity CLI, Codex CLI…", port=port)
        + "\n\n"
        + tr("Claude Code (in a terminal):") + "\n"
        + f"    claude mcp add ingetrazo -- {quoted}\n\n"
        + tr("Antigravity CLI (Google; in a terminal):") + "\n"
        + f"    agy mcp add ingetrazo -- {quoted}\n\n"
        + tr("Claude Desktop: add this to {path} and restart Claude Desktop:",
             path=desktop_config_path(platform)) + "\n"
        + json.dumps(config, indent=2) + "\n\n"
        + tr("Other clients take the same block in their own file:") + "\n"
        + others + "\n\n"
        + tr("The companion obtains a short-lived local credential "
             "automatically; it is not included in this configuration.")
        + "\n\n"
        + tr("Keep IngeTrazo open with the bridge on; the tools answer only while it runs.")
    )


def _bridge_of(viewport) -> _Bridge:
    window = viewport.window()
    bridge = getattr(window, "_ai_bridge", None)
    if bridge is None:
        bridge = _Bridge(viewport)
        window._ai_bridge = bridge
    return bridge


class BridgeSection(QWidget):
    """The bridge's part of the «AI» tab: on/off, where it listens, and
    the exact lines to paste into the MCP client — the user who reached
    this is rarely the one who knows them by heart."""

    def __init__(self, viewport, parent=None) -> None:
        super().__init__(parent)
        self._viewport = viewport
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 0, 4, 4)
        self.section = FoldSection(tr("AI bridge (MCP)"), "ia/open_bridge",
                                   default_open=False)
        lay.addWidget(self.section)
        body = QVBoxLayout(self.section.body)
        self._status = QLabel()
        self._status.setWordWrap(True)
        body.addWidget(self._status)
        self._activity = QLabel()
        self._activity.setWordWrap(True)
        body.addWidget(self._activity)
        self._legacy_writes = QCheckBox(tr(
            "Allow raw Python, undo and redo for this session"))
        self._legacy_writes.setToolTip(tr(
            "Advanced: lets the connected MCP client change the document "
            "through legacy tools. This resets to off when the bridge stops."))
        self._legacy_writes.toggled.connect(self._on_legacy_writes)
        body.addWidget(self._legacy_writes)
        row = QHBoxLayout()
        self._toggle = QPushButton()
        self._toggle.clicked.connect(self.toggle)
        row.addWidget(self._toggle)
        self._copy = QPushButton(tr("Copy"))
        self._copy.setToolTip(tr("Copy the connection instructions"))
        self._copy.clicked.connect(self._on_copy)
        row.addWidget(self._copy)
        body.addLayout(row)
        self._text = QPlainTextEdit()
        self._text.setReadOnly(True)
        self._text.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self._text.setMinimumHeight(140)
        body.addWidget(self._text)
        narrow(self._toggle, self._copy)
        self._refresh()

    @property
    def running(self) -> bool:
        bridge = getattr(self._viewport.window(), "_ai_bridge", None)
        return bridge is not None and bridge.running

    def start(self) -> bool:
        bridge = _bridge_of(self._viewport)
        if bridge.running:
            return True
        try:
            port = bridge.start()
        except OSError as exc:
            self._viewport.flash_status(tr(
                "AI bridge could not start: {err}", err=str(exc)))
            self._refresh(error=str(exc))
            return False
        self._port = port
        if getattr(self, "_activity_bridge", None) is not bridge:
            bridge.activity_changed.connect(self._on_activity)
            self._activity_bridge = bridge
        self._viewport.flash_status(tr(
            "AI bridge listening on 127.0.0.1:{port}", port=port), 8000)
        self._refresh()
        return True

    def stop(self) -> None:
        bridge = getattr(self._viewport.window(), "_ai_bridge", None)
        if bridge is not None and bridge.running:
            bridge.allow_legacy_writes = False
            bridge.stop()
            self._viewport.flash_status(tr("AI bridge stopped"))
        self._refresh()

    def _on_legacy_writes(self, checked: bool) -> None:
        bridge = getattr(self._viewport.window(), "_ai_bridge", None)
        if bridge is not None:
            bridge.allow_legacy_writes = bool(checked) and bridge.running
            self._on_activity(bridge.activity())

    def _on_activity(self, state: dict) -> None:
        if not state.get("connected"):
            text = tr("No MCP client connected")
        else:
            text = tr("{client} connected — {count} requests",
                      client=state.get("client_name") or "MCP client",
                      count=state.get("request_count", 0))
        if state.get("last_tool"):
            text += tr(" — last tool: {tool}", tool=state["last_tool"])
        if state.get("last_error"):
            text += tr(" — error: {err}", err=state["last_error"])
        self._activity.setText(text)

    def toggle(self) -> None:
        if self.running:
            self.stop()
        else:
            self.start()

    def _refresh(self, error: str | None = None) -> None:
        on = self.running
        self._toggle.setText(tr("Stop bridge") if on else tr("Start bridge"))
        self._copy.setVisible(on)
        self._text.setVisible(on)
        self._activity.setVisible(on)
        self._legacy_writes.setVisible(on)
        if on:
            port = getattr(self, "_port", DEFAULT_PORT)
            self._status.setText(tr(
                "Listening on 127.0.0.1:{port} — connect your MCP client "
                "with the lines below.", port=port))
            self._text.setPlainText(connect_instructions(port))
            bridge = getattr(self._viewport.window(), "_ai_bridge", None)
            if bridge is not None:
                self._legacy_writes.blockSignals(True)
                self._legacy_writes.setChecked(bridge.allow_legacy_writes)
                self._legacy_writes.blockSignals(False)
                self._on_activity(bridge.activity())
        elif error:
            self._status.setText(tr(
                "AI bridge could not start: {err}", err=error))
        else:
            self._legacy_writes.blockSignals(True)
            self._legacy_writes.setChecked(False)
            self._legacy_writes.blockSignals(False)
            self._status.setText(tr(
                "Off. Start it to let an AI agent (Claude, Cursor, "
                "Antigravity…) model in this document over MCP."))

    def _on_copy(self) -> None:
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(self._text.toPlainText())
        self._viewport.flash_status(tr("Copied"))


def setup(app) -> None:
    """The bridge joins the assistant in the side tray's «AI» tab; the
    Extensions entry opens that section and starts the bridge."""
    section = BridgeSection(app.viewport)
    dock = app.add_panel(tr("AI"), section, panel="ai")
    app.window._ai_bridge_section = section

    def summon() -> None:
        app.show_panel(dock)
        section.section.set_open(True)
        section.start()

    app.add_menu_action(tr("AI Bridge (MCP)"), summon, tip=tr(
        "Start the local bridge through which an AI agent (MCP) drives "
        "the open document."))
