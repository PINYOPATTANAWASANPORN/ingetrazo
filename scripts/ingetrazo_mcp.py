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
    "get_document_context. Para una intención corta usa create_task y después "
    "propose_actions con el task_id y el alcance devueltos: "
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
        "name": "create_task",
        "description": (
            "Turn compact user intent into a revision-pinned task contract. "
            "Scope may be auto, selection, current_group, visible_model, "
            "whole_model, or {kind: entities, entity_ids: [...]}. Auto prefers "
            "stable selected containers, then the open group, then visible "
            "model. Returns the resolved IDs, classified goal, assumptions, "
            "acceptance criteria, and a small role plan without changing the "
            "document."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "intent": {"type": "string", "minLength": 1,
                           "maxLength": 1000},
                "scope": {"oneOf": [
                    {"type": "string", "enum": ["auto", "selection",
                     "current_group", "visible_model", "whole_model"]},
                    {"type": "object", "properties": {
                        "kind": {"const": "entities"},
                        "entity_ids": {"type": "array",
                                       "items": {"type": "string"}}},
                     "required": ["kind", "entity_ids"]}]},
                "goal": {"type": "string", "enum": ["create", "revise",
                         "furnish", "check", "quantify", "explain"]},
                "constraints": {},
                "execution": {"type": "string", "enum": ["analysis_only",
                              "preview_first", "apply_safe_changes"]},
                "assumptions": {"type": "array",
                                "items": {"type": "string"},
                                "maxItems": 20},
                "acceptance_criteria": {"type": "array",
                                        "items": {"type": "string"},
                                        "maxItems": 20},
            },
            "required": ["intent"],
        },
    },
    {
        "name": "get_task",
        "description": (
            "Read a task contract and its current lifecycle status. Reports "
            "whether the live document has made its base revision stale."),
        "inputSchema": {"type": "object", "properties": {
            "task_id": {"type": "string"}}, "required": ["task_id"]},
    },
    {
        "name": "begin_specialist_review",
        "description": (
            "Begin read-only external review of an analysis_only task. Returns one "
            "bounded metadata snapshot and two role assignments with submission tokens. "
            "The external coordinator dispatches specialists (possibly in parallel); "
            "IngeTrazo does not call a provider here. Pass each role its snapshot and "
            "own token, then submit findings. Tokens correlate roles, not trusted identities. "
            "Same task retries reuse the review. No document changes or provider credentials."),
        "inputSchema": {"type": "object", "properties": {
            "task_id": {"type": "string"}}, "required": ["task_id"],
            "additionalProperties": False},
    },
    {
        "name": "submit_specialist_review",
        "description": (
            "Submit a role's read-only findings for the assigned snapshot. Result is "
            "{summary,findings:[{entity_id,topic,verdict,evidence}]} or {error}. "
            "At most 20 findings using snapshot IDs; summary <=1000 characters, "
            "evidence <=500, error <=300. Topics: structure/tag/material/requirements; "
            "verdicts: clear/concern/unknown. Use unknown for missing evidence; metadata "
            "does not prove geometry or regulatory compliance. No actions or code. "
            "Identical retries are idempotent; conflicting resubmissions fail. Both roles "
            "complete the report automatically and disagreements remain unresolved. "
            "Stale/cancelled reviews reject late results."),
        "inputSchema": {"type": "object", "properties": {
            "review_id": {"type": "string"},
            "role": {"type": "string", "enum": ["model_structure", "task_requirements"]},
            "submission_token": {"type": "string"},
            "snapshot_id": {"type": "string"},
            "result": {"type": "object"}},
            "required": ["review_id", "role", "submission_token", "snapshot_id", "result"],
            "additionalProperties": False},
    },
    {
        "name": "get_specialist_review",
        "description": "Read role submission status and the combined report; rechecks document revision. Never returns role tokens.",
        "inputSchema": {"type": "object", "properties": {
            "review_id": {"type": "string"}}, "required": ["review_id"],
            "additionalProperties": False},
    },
    {
        "name": "export_specialist_review",
        "description": (
            "Return a versioned JSON review bundle with role findings, conflicts, "
            "revision and an unsigned SHA-256 payload checksum. Only finished current "
            "reviews can export. Excludes connection settings, role tokens and raw snapshots; "
            "review prose is included. Returns data only, never writes a file."),
        "inputSchema": {"type": "object", "properties": {
            "review_id": {"type": "string"}}, "required": ["review_id"],
            "additionalProperties": False},
    },
    {
        "name": "cancel_specialist_review",
        "description": (
            "Cancel a collecting review and reject late submissions. Does not stop an "
            "external provider request: the coordinator must cancel those separately. "
            "Does not modify geometry or history."),
        "inputSchema": {"type": "object", "properties": {
            "review_id": {"type": "string"}}, "required": ["review_id"],
            "additionalProperties": False},
    },
    {
        "name": "propose_actions",
        "description": (
            "Propose bounded edits or primitive creation without changing the document. "
            "Supported actions: rename_entities {name}, set_visibility "
            "{visible}, set_lock {locked}, assign_tag {tag}, "
            "assign_material {material}, transform_entities, create_box with "
            "name/origin/size, and create_cylinder with name/origin/radius/"
            "height/segments; create_slab with name/origin/size=[width,depth,thickness]; "
            "create_wall with name/start/end/height/thickness and optional openings "
            "[{offset,sill,width,height}]. Wall thickness extends left of start->end; "
            "sill=0 makes a door. Openings must fit inside and not overlap or touch. "
            "Creation may include tag, material and component. "
            "create_component_instance uses name/source_id/offset to copy a top-level "
            "component by a model-space translation, preserving its shared mesh. "
            "A transform "
            "targets one top-level entity and uses operation=translate with "
            "delta=[x,y,z], rotate with center/axis/degrees, or scale with "
            "center/factor. Existing-entity actions also need entity_ids; "
            "creation defaults to coordinate_space=model. Nested creation requires "
            "coordinate_space=parent and parent_id naming a non-component instance "
            "container outside shared component definitions. Close group editing first. Holds one "
            "document write lease. When task_id came from create_task, every "
            "entity must remain inside that task's resolved scope. It "
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
    return _tool_result(json.dumps(result, indent=2, ensure_ascii=False),
                        is_error=result.get("ok") is False)


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
