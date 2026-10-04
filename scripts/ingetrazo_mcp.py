#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""IngeTrazo MCP server — connect Claude (Code / Desktop) to the live app.

Stdlib-only stdio MCP server: it bridges the Model Context Protocol to the
AI Bridge plugin's localhost TCP port (start it first: IngeTrazo ▸
Extensiones ▸ "AI Bridge (MCP)").

Register it with Claude Code:

    claude mcp add ingetrazo -- python3 /path/to/app/scripts/ingetrazo_mcp.py

Tools include bounded model context and preview-first typed property changes,
plus the legacy run_python, query_model, screenshot, undo and redo profile.
Typed commits require the user's in-app Apply action and become one undo step.
The helper authenticates each request with a short-lived local session
credential. Legacy mutation tools remain unavailable until the user enables
them in IngeTrazo.
"""
from __future__ import annotations

import base64
import json
import os
import socket
import sys
from pathlib import Path

PORT = int(os.environ.get("INGETRAZO_AI_PORT", 4763))
#: Where the bridge is. It only ever listens on the app machine's loopback
#: and requires the rotating local session credential; a client in
#: a container or on another machine reaches it through a tunnel the user
#: sets up, and names the tunnel's end here (issue #130).
HOST = os.environ.get("INGETRAZO_AI_HOST", "").strip() or "127.0.0.1"
PROTOCOL = "2024-11-05"

# The recipe book the model needs, from the app's own copy — the SAME text
# the in-app assistant teaches (core/ai_recipes.py explains what its absence
# cost). This process is stdlib-only and starts from four layouts (checkout,
# PyInstaller bundle, AppImage, Flatpak), so the app root goes on the path
# first; if that import ever fails the server still answers, with the short
# reference it can state truthfully.
_APP_ROOT = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, _APP_ROOT)
try:
    from core.ai_recipes import reference as _reference
    REFERENCE = _reference("llamada")
except ImportError:                             # pragma: no cover - packaging
    REFERENCE = ("IngeTrazo: Z arriba, unidades en METROS. En el scope: "
                 "scene, mesh, selection, groups, layers, viewport, "
                 "QVector3D, Mesh, Group, Edge, Face, bim. Recetario: "
                 "revolve / extrude / prism / wall / house.")
try:
    from core.ai_bridge_auth import read_credential as _read_credential
except ImportError:                             # pragma: no cover - packaging
    _read_credential = None
finally:
    if sys.path and sys.path[0] == _APP_ROOT:   # leave the process as found
        del sys.path[0]

#: MCP's ``initialize`` hands this to the client before any tool is listed —
#: the stance, with the recipes themselves on ``run_python`` where every
#: client is sure to put them in front of the model.
INSTRUCTIONS = (
    "Estas herramientas operan el documento ABIERTO de IngeTrazo, en vivo: "
    "lo que escribas aparece en la pantalla del usuario y entra en su "
    "historial de deshacer.\n" + REFERENCE + "\nEmpieza por "
    "get_document_context. Para propiedades compatibles usa propose_actions: "
    "IngeTrazo muestra la vista previa y solamente el usuario puede aplicarla. "
    "Usa screenshot para comprobar el resultado.")

TOOLS = [
    {
        "name": "run_python",
        "description": (
            "Execute Python against the LIVE IngeTrazo document (Z-up, "
            "metres). Disabled by default; the user must enable legacy "
            "write tools in the bridge panel for this session. Returns "
            "stdout/stderr. The reference below is "
            "everything you need — read it instead of exploring the API.\n\n"
            + REFERENCE),
        "inputSchema": {
            "type": "object",
            "properties": {"code": {"type": "string"}},
            "required": ["code"],
        },
    },
    {
        "name": "query_model",
        "description": ("Model overview: entity counts, group/component "
                        "names, materials, layers, bounds, selection size."),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_document_context",
        "description": ("Bounded, paginated context for the live document: "
                        "revisions, units, active tag, selection, layers and "
                        "the group/component outline. Start here instead of "
                        "discovering the Python API."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "minimum": 1,
                          "maximum": 200},
                "cursor": {"type": "string"},
            },
        },
    },
    {
        "name": "find_entities",
        "description": ("Find groups or components by a name fragment, "
                        "stable ID, or tag. Results are paginated and "
                        "read-only."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1,
                          "maximum": 200},
                "cursor": {"type": "string"},
            },
        },
    },
    {
        "name": "get_entities",
        "description": ("Get detail for stable group/component IDs returned "
                        "by document context or entity search."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "entity_ids": {"type": "array",
                               "items": {"type": "string"},
                               "maxItems": 200},
            },
            "required": ["entity_ids"],
        },
    },
    {
        "name": "get_capabilities",
        "description": ("Read the AI bridge feature contract, including "
                        "stable entity types and whether write actions, "
                        "preview, or multi-agent work are available."),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "propose_actions",
        "description": (
            "Propose bounded property edits without changing the document. "
            "Supported actions: rename_entities {name}, set_visibility "
            "{visible}, set_lock {locked}, assign_tag {tag}; every action "
            "also needs entity_ids. Holds one document write lease and "
            "returns the exact before/after preview."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "maxLength": 100},
                "intent": {"type": "string"},
                "base_revision": {"type": "integer"},
                "idempotency_key": {"type": "string", "minLength": 8,
                                    "maxLength": 200},
                "actions": {"type": "array", "minItems": 1,
                            "maxItems": 100,
                            "items": {"type": "object"}},
            },
            "required": ["task_id", "base_revision", "idempotency_key",
                         "actions"],
        },
    },
    {
        "name": "preview_changes",
        "description": "Read a task's exact non-mutating before/after preview.",
        "inputSchema": {"type": "object", "properties": {
            "task_id": {"type": "string"}}, "required": ["task_id"]},
    },
    {
        "name": "validate_changes",
        "description": "Revalidate a proposed task against the live revision.",
        "inputSchema": {"type": "object", "properties": {
            "task_id": {"type": "string"}}, "required": ["task_id"]},
    },
    {
        "name": "commit_changes",
        "description": (
            "Request commit of a validated preview. This never bypasses the "
            "user: IngeTrazo displays Apply/Discard and only Apply commits "
            "the change set as one undo step."),
        "inputSchema": {"type": "object", "properties": {
            "task_id": {"type": "string"},
            "base_revision": {"type": "integer"},
            "idempotency_key": {"type": "string"}},
            "required": ["task_id", "base_revision", "idempotency_key"]},
    },
    {
        "name": "discard_changes",
        "description": "Discard a proposal and release its write lease.",
        "inputSchema": {"type": "object", "properties": {
            "task_id": {"type": "string"}}, "required": ["task_id"]},
    },
    {
        "name": "screenshot",
        "description": ("Render the current viewport and LOOK at it — use "
                        "after building to verify and iterate."),
        "inputSchema": {
            "type": "object",
            "properties": {"width": {"type": "integer"},
                           "height": {"type": "integer"}},
        },
    },
    {
        "name": "undo",
        "description": "Undo the last step in IngeTrazo.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "redo",
        "description": "Redo the last undone step in IngeTrazo.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]

_sock: socket.socket | None = None
_req_id = 0
_client_name = "MCP client"


def _session() -> dict:
    """Read the short-lived credential without printing or persisting it."""
    if _read_credential is None:
        raise OSError("AI bridge credential support is missing from this "
                      "installation")
    try:
        return _read_credential()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise OSError("AI bridge is off or its session credential is "
                      f"unavailable: {exc}") from exc


def _bridge(tool: str, args: dict) -> dict:
    """One request to the in-app bridge (reconnecting once if it dropped)."""
    global _sock, _req_id
    for attempt in (0, 1):
        session = _session()
        if _sock is None:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(180.0)
            port = PORT if PORT != 4763 else session["port"]
            s.connect((HOST, port))
            _sock = s
        _req_id += 1
        try:
            _sock.sendall((json.dumps(
                {"id": _req_id, "tool": tool, "args": args,
                 "auth": session["token"],
                 "client": _client_name}) + "\n").encode())
            buf = b""
            while b"\n" not in buf:
                chunk = _sock.recv(65536)
                if not chunk:
                    raise OSError("bridge closed the connection")
                buf += chunk
            return json.loads(buf.split(b"\n", 1)[0])
        except OSError:
            try:
                _sock.close()
            except OSError:
                pass
            _sock = None
            if attempt:
                raise
    raise OSError("unreachable")


def _tool_result(text: str, is_error: bool = False) -> dict:
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


def _call(name: str, args: dict) -> dict:
    try:
        reply = _bridge(name, args)
    except OSError as exc:
        return _tool_result(
            "Cannot reach IngeTrazo's AI bridge on %s:%d (%s). "
            "In IngeTrazo: the AI tab of the side tray > Start bridge (or Extensions > AI Bridge (MCP))."
            % (HOST, PORT, exc), is_error=True)
    if not reply.get("ok"):
        return _tool_result(str(reply.get("error")), is_error=True)
    result = reply.get("result") or {}
    if name == "screenshot" and result.get("path"):
        try:
            with open(result["path"], "rb") as fh:
                data = base64.b64encode(fh.read()).decode()
            return {"content": [{"type": "image", "data": data,
                                 "mimeType": "image/png"}]}
        except OSError as exc:
            return _tool_result(f"screenshot unreadable: {exc}",
                                is_error=True)
    if name == "run_python":
        parts = []
        if result.get("stdout"):
            parts.append(result["stdout"].rstrip())
        if result.get("stderr"):
            parts.append("stderr:\n" + result["stderr"].rstrip())
        if result.get("error"):
            parts.append("ROLLED BACK — the document is unchanged: "
                         + str(result["error"]))
        parts.append("(changed: %s)" % result.get("changed"))
        return _tool_result("\n".join(p for p in parts if p),
                            is_error=bool(result.get("error")))
    return _tool_result(json.dumps(result, indent=2, ensure_ascii=False))


def handle(msg: dict) -> dict | None:
    """One JSON-RPC message → the reply dict (None for notifications)."""
    global _client_name
    method = msg.get("method")
    msg_id = msg.get("id")
    if method == "initialize":
        info = (msg.get("params") or {}).get("clientInfo") or {}
        name = str(info.get("name") or "MCP client")[:80]
        version = str(info.get("version") or "")[:32]
        _client_name = f"{name} {version}".strip()
        return {"jsonrpc": "2.0", "id": msg_id, "result": {
            "protocolVersion": PROTOCOL,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "ingetrazo", "version": "1.0.0"},
            "instructions": INSTRUCTIONS,
        }}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": msg_id,
                "result": {"tools": TOOLS}}
    if method == "tools/call":
        params = msg.get("params") or {}
        result = _call(params.get("name", ""),
                       params.get("arguments") or {})
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}
    if msg_id is None:          # notification (initialized, cancelled, ...)
        return None
    return {"jsonrpc": "2.0", "id": msg_id,
            "error": {"code": -32601, "message": f"unknown {method}"}}


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        reply = handle(msg)
        if reply is not None:
            sys.stdout.write(json.dumps(reply) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
