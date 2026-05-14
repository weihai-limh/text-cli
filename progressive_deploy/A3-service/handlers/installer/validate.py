"""Validate an instruction package before installation."""

from __future__ import annotations

import json
import pathlib
from typing import Optional

# Accepted runtime values from schema.json
ACCEPTED_RUNTIMES = frozenset({"python", "node", "js", "mcp", "cmd"})

# Domains that MUST NOT be installed as packages (system reserved)
SYSTEM_DOMAINS = frozenset({"text-cli"})

# Default search paths for package sources
DEFAULT_SOURCE_DIRS = [
    pathlib.Path("/root/.openclaw/workspace/tide-scripts/text-cliV1"),
]


def _find_package_dir(name: str, source_dirs: list[pathlib.Path] = None):
    """Locate a package directory by name across source dirs."""
    if source_dirs is None:
        source_dirs = DEFAULT_SOURCE_DIRS
    for sdir in source_dirs:
        candidate = sdir / name
        if candidate.is_dir():
            return candidate
    return None


def _check_mcporter_server(server_name: str) -> tuple[bool, str]:
    """Verify an MCP server is configured in mcporter."""
    import subprocess
    # mcporter config is in workspace, not service dir
    mcporter_config = "/root/.openclaw/workspace/config/mcporter.json"
    try:
        result = subprocess.run(
            ["mcporter", "--config", mcporter_config, "list", server_name],
            capture_output=True, text=True, timeout=35,
        )
        if result.returncode == 0 and "function" in result.stdout:
            return True, "ok"
        return False, f"MCP server '{server_name}' not configured or unreachable in mcporter"
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        return False, f"Cannot check MCP server '{server_name}': {e}"


def validate_package(name: str, source_dirs: list[pathlib.Path] = None) -> tuple[bool, str, Optional[dict]]:
    """Validate a package for installation.

    Returns (ok, message, schema_dict_or_none).
    """
    # 1. Find package directory
    pkg_dir = _find_package_dir(name, source_dirs)
    if pkg_dir is None:
        searched = ", ".join(str(d) for d in (source_dirs or DEFAULT_SOURCE_DIRS))
        return False, f"Package not found \"{name}\"。Searched: {searched}", None

    # 2. schema.json required (for all runtime types)
    schema_path = pkg_dir / "schema.json"
    if not schema_path.is_file():
        return False, f"包 \"{name}\" Missing schema.json", None

    # 3. Parse and validate schema
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        return False, f"schema.json Parse error: {e}", None

    # 4. Check runtime
    runtime = schema.get("runtime", "")
    if runtime not in ACCEPTED_RUNTIMES:
        return False, f"Unsupported runtime \"{runtime}\"（Accepted: python/node/mcp/cmd）", None

    # 5. Check system domain protection
    pkg_id = schema.get("id", "")
    if pkg_id in SYSTEM_DOMAINS:
        return False, f"\"{pkg_id}\" 是system reserved domain, cannot be installed as package", None

    # 6. Check directives
    directives = schema.get("directives", [])
    if not directives:
        return False, f"包 \"{name}\" No directives declared", None

    # 7. Runtime-specific validation
    meta = {
        "path": str(pkg_dir),
        "schema": schema,
        "schema_path": str(schema_path),
        "handler_path": None,
        "req_path": None,
        "service_descriptor": None,
    }

    if runtime == "python":
        # Python packages require handler.py
        handler_path = pkg_dir / "handler.py"
        if not handler_path.is_file():
            return False, f"包 \"{name}\" (runtime=python) Missing handler.py", None
        meta["handler_path"] = str(handler_path)
        req_path = pkg_dir / "requirements.txt"
        if req_path.is_file():
            meta["req_path"] = str(req_path)

    elif runtime == "mcp":
        # MCP packages require service-descriptor.json and mcporter config
        sd_path = pkg_dir / "service-descriptor.json"
        if not sd_path.is_file():
            return False, f"包 \"{name}\" (runtime=mcp) Missing service-descriptor.json", None
        try:
            sd = json.loads(sd_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            return False, f"service-descriptor.json Parse error: {e}", None

        mcp_server = sd.get("mcp_server", "")
        if not mcp_server:
            return False, f"service-descriptor.json Missing mcp_server field", None

        # Verify mcporter has this server
        ok, msg = _check_mcporter_server(mcp_server)
        if not ok:
            return False, f"安装失败: {msg}。Please first configure in mcporter: '{mcp_server}' connection.", None

        meta["service_descriptor"] = sd
        meta["handler_path"] = None  # MCP has no local handler

    elif runtime == "node":
        # Node.js packages require handler.js
        handler_path = pkg_dir / "handler.js"
        if not handler_path.is_file():
            return False, f"包 \"{name}\" (runtime=node) 缺少 handler.js", None
        meta["handler_path"] = str(handler_path)
        # package.json optional for npm dependencies
        pkg_json = pkg_dir / "package.json"
        if pkg_json.is_file():
            meta["npm_dir"] = str(pkg_dir)

    elif runtime == "cmd":
        # cmd packages require whitelist.json (safety boundary for CLI exec)
        wl_path = pkg_dir / "whitelist.json"
        if not wl_path.is_file():
            return False, f"包 \"{name}\" (runtime=cmd) Missing whitelist.json", None
        try:
            wl = json.loads(wl_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            return False, f"whitelist.json Parse error: {e}", None
        if not wl.get("tool") or not wl.get("commands"):
            return False, f"whitelist.json 缺少 tool/commands 字段", None
        meta["whitelist_path"] = str(wl_path)
        meta["whitelist"] = wl

    elif runtime == "js":
        return False, "JS runtime 暂未支持"

    return True, "ok", meta
