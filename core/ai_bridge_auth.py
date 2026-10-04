# SPDX-License-Identifier: GPL-3.0-or-later
"""Short-lived local credentials for the in-app AI bridge.

The desktop process and the stdio MCP helper meet through one owner-readable
session file.  The secret is rotated whenever the bridge starts, is never
printed in connection instructions, and disappears when the bridge stops.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path


def credential_path() -> Path:
    override = os.environ.get("INGETRAZO_AI_CREDENTIAL_FILE", "").strip()
    if override:
        return Path(override)
    home = Path.home()
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("LOCALAPPDATA") or
                    home / "AppData" / "Local") / "IngeTrazo"
    elif sys.platform == "darwin":
        base = home / "Library" / "Application Support" / "IngeTrazo"
    else:
        base = Path(os.environ.get("XDG_RUNTIME_DIR") or
                    Path(tempfile.gettempdir()) / f"ingetrazo-{os.getuid()}")
    return base / "ai-bridge-session.json"


def write_credential(token: str, port: int) -> Path:
    """Atomically publish a new session credential with private mode bits."""
    path = credential_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.parent.chmod(0o700)
    except OSError:
        pass
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps({"token": token, "port": int(port),
                               "pid": os.getpid()}), encoding="utf-8")
    try:
        tmp.chmod(0o600)
    except OSError:
        pass
    tmp.replace(path)
    return path


def read_credential() -> dict:
    """Read and minimally validate the credential published by IngeTrazo."""
    data = json.loads(credential_path().read_text(encoding="utf-8"))
    token = data.get("token")
    port = data.get("port")
    if not isinstance(token, str) or len(token) < 32:
        raise ValueError("invalid AI bridge session token")
    if not isinstance(port, int) or not 0 < port < 65536:
        raise ValueError("invalid AI bridge port")
    return {"token": token, "port": port, "pid": data.get("pid")}


def remove_credential(token: str) -> None:
    """Remove only this bridge's file, never a newer process's session."""
    path = credential_path()
    try:
        current = json.loads(path.read_text(encoding="utf-8"))
        if current.get("token") == token:
            path.unlink()
    except (OSError, ValueError):
        pass
