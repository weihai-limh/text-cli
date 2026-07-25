"""Validate an instruction package before installation."""

from __future__ import annotations

import json
import logging
import os
import pathlib
import subprocess

logger = logging.getLogger(__name__)

# Accepted runtime values from schema.json
ACCEPTED_RUNTIMES = frozenset({"python", "node", "js", "mcp", "cmd"})

# Domains that MUST NOT be installed as packages (system reserved)
SYSTEM_DOMAINS = frozenset({"text-cli"})


def _get_source_dirs() -> list[pathlib.Path]:
    raw = os.environ.get("TEXT_CLI_PACKAGE_SOURCE_DIRS", "")
    if raw:
        return [pathlib.Path(d.strip()) for d in raw.split(os.pathsep) if d.strip()]
    return []


def _find_package_dir(name: str, source_dirs: list[pathlib.Path] = None):
    """Locate a package directory by name across source dirs. Recursively searches subdirectories, matching by directory name or schema id."""
    if source_dirs is None:
        source_dirs = _get_source_dirs()
    for sdir in source_dirs:
        if not sdir.is_dir():
            continue
        for candidate in sdir.rglob("schema.json"):
            if candidate.parent.name == name:
                return candidate.parent
            try:
                schema = json.loads(candidate.read_text(encoding="utf-8"))
                if schema.get("id") == name:
                    return candidate.parent
            except Exception as e:
                logger.debug("Failed to parse schema candidate %s: %s", candidate, e)
                pass
    return None


def _check_mcporter_server(server_name: str) -> tuple[bool, str]:
    """Verify an MCP server is configured in mcporter.

    Uses the same 3-layer resolution as mcp_handler._resolve_mcporter().
    Warns but does not block install if mcporter unavailable.
    """
    from handlers.mcp_handler import _resolve_mcporter

    try:
        mcporter_bin, _ = _resolve_mcporter()
    except FileNotFoundError:
        return True, "mcporter not available — MCP dispatch may fail"

    try:
        result = subprocess.run(
            [mcporter_bin, "list", server_name],
            capture_output=True, text=True, timeout=35, check=False,
        )
        if result.returncode == 0 and "function" in result.stdout:
            return True, "ok"
        return True, f"mcporter: server '{server_name}' not configured — MCP dispatch may fail"
    except (subprocess.TimeoutExpired, OSError) as e:
        return True, f"mcporter check skipped ({e}) — MCP dispatch may fail"


def validate_package(name: str, source_dirs: list[pathlib.Path] = None) -> tuple[bool, str, dict | None]:
    """Validate a package for installation.

    Returns (ok, message, schema_dict_or_none).
    """
    # 1. Find package directory
    pkg_dir = _find_package_dir(name, source_dirs)
    if pkg_dir is None:
        searched = ", ".join(str(d) for d in (source_dirs or _get_source_dirs()))
        if not searched:
            return False, "TEXT_CLI_PACKAGE_SOURCE_DIRS env var not set. Set it to the directive package directory (e.g. /home/xxx/text-cli-package/new-package)", None
        return False, f"Package not found \"{name}\"。Searched: {searched}", None

    # 2. schema.json required (for all runtime types)
    schema_path = pkg_dir / "schema.json"
    if not schema_path.is_file():
        return False, f"package \"{name}\" Missing schema.json", None

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
        return False, f"\"{pkg_id}\" is a system reserved domain, cannot be installed as package", None

    # 6. Check directives
    directives = schema.get("directives", [])
    if not directives:
        return False, f"package \"{name}\" No directives declared", None

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
            return False, f"package \"{name}\" (runtime=python) Missing handler.py", None
        meta["handler_path"] = str(handler_path)
        req_path = pkg_dir / "requirements.txt"
        if req_path.is_file():
            meta["req_path"] = str(req_path)

    elif runtime == "mcp":
        # MCP packages require service-descriptor.json and mcporter config
        sd_path = pkg_dir / "service-descriptor.json"
        if not sd_path.is_file():
            return False, f"package \"{name}\" (runtime=mcp) Missing service-descriptor.json", None
        try:
            sd = json.loads(sd_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            return False, f"service-descriptor.json Parse error: {e}", None

        mcp_server = sd.get("mcp_server", "")
        if not mcp_server:
            return False, "service-descriptor.json Missing mcp_server field", None

        # Verify mcporter has this server
        ok, msg = _check_mcporter_server(mcp_server)
        if not ok:
            return False, f"installation failed: {msg}.Please first configure in mcporter: '{mcp_server}' connection.", None

        meta["service_descriptor"] = sd
        meta["handler_path"] = None  # MCP has no local handler

    elif runtime == "node":
        entry = schema.get("entry", "handler.js")
        handler_path = pkg_dir / entry
        if not handler_path.is_file():
            return False, f"package \"{name}\" (runtime=node) missing {entry}", None
        meta["handler_path"] = str(handler_path)
        pkg_json = pkg_dir / "package.json"
        if pkg_json.is_file():
            meta["npm_dir"] = str(pkg_dir)

    elif runtime == "cmd":
        # cmd packages require whitelist.json (safety boundary for CLI exec)
        wl_path = pkg_dir / "whitelist.json"
        if not wl_path.is_file():
            return False, f"package \"{name}\" (runtime=cmd) Missing whitelist.json", None
        try:
            wl = json.loads(wl_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            return False, f"whitelist.json Parse error: {e}", None
        if not wl.get("tool") or not wl.get("commands"):
            return False, "whitelist.json missing tool/commands field", None
        meta["whitelist_path"] = str(wl_path)
        meta["whitelist"] = wl

    elif runtime == "js":
        return False, "JS runtime not yet supported"

    return True, "ok", meta
