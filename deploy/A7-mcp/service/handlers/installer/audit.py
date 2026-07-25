"""Append-only audit log for install/uninstall operations.

Format: JSON Lines (one JSON object per line, append-only).
"""

from __future__ import annotations

import json
import os
import pathlib
import time

_PROJECT = pathlib.Path(os.environ.get("TEXT_CLI_HOME", str(pathlib.Path.home() / "text-cli")))
AUDIT_PATH = _PROJECT / "service" / ".install_audit.jsonl"


def log_install(name: str, meta: dict, success: bool, message: str):
    """Record an install operation."""
    _append({
        "ts": time.time(),
        "ts_human": _ts_human(),
        "op": "install",
        "name": name,
        "runtime": meta.get("schema", {}).get("runtime", "?"),
        "success": success,
        "message": message,
    })


def log_uninstall(name: str, success: bool, message: str):
    """Record an uninstall operation."""
    _append({
        "ts": time.time(),
        "ts_human": _ts_human(),
        "op": "uninstall",
        "name": name,
        "success": success,
        "message": message,
    })


def _append(entry: dict):
    try:
        with open(AUDIT_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass  # audit failure must not block the operation


def _ts_human() -> str:
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
