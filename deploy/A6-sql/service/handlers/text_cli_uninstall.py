"""
text-cli;uninstall — 平台自管理：卸载指令包。

移除 handler.py + schema.json，保留审计记录。
受保护的系统域（text-cli）不可卸载。

Directives:
    AI:text-cli;uninstall,<包名>     → 卸载指定包
    AI:文本指令;卸载,<包名>           → 中文别名

Author: Tide 🌊
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from core.registry import directive

logger = logging.getLogger(__name__)

from .installer.audit import log_uninstall
from .installer.filesystem import remove_files
from .installer.validate import SYSTEM_DOMAINS
from .package_manifest import remove as manifest_remove

_INITS_PATH = Path(__file__).resolve().parent.parent / "config" / "handler_inits.py"


@directive("text-cli", "uninstall", domain_alias="文本指令", action_aliases={"uninstall": "卸载"})
def text_cli_uninstall(params: list[str]) -> str:
    """Uninstall an instruction package by name."""
    import json

    from core.registry import unregister as _registry_unregister

    if not params:
        return "usage: AI:text-cli;uninstall,<package>\n\n" \
               "Use AI:text-cli;query to view installed packages."

    name = params[0].strip()

    # 1. System domain protection
    if name in SYSTEM_DOMAINS:
        log_uninstall(name, False, "rejected: system domain")
        return f"\"{name}\" is a system reserved domain, cannot be uninstalled."

    # Unregister in-memory registry entries
    safe = name.replace("-", "_")
    schema_path = Path(__file__).resolve().parent / "schema" / f"{safe}_schema.json"
    _was_mcp = False
    try:
        schema_data = json.loads(schema_path.read_text(encoding="utf-8"))
        _was_mcp = schema_data.get("runtime") == "mcp"
        for d in schema_data.get("directives", []):
            _registry_unregister(d.get("domain", name), d.get("action", ""))
    except Exception as e:
        logger.debug("Failed to parse schema for uninstall '%s': %s", name, e)
        pass

    # Drop tables first (before remove_files deletes the schema file)
    from .installer.filesystem import _drop_tables
    tbl_msg = ""
    try:
        ok_tbl, tbl_msg = _drop_tables(schema_path, name)
    except Exception as e:
        logger.debug("Failed to drop tables for '%s': %s", name, e)
        pass

    ok, msg = remove_files(name)
    if not ok:
        log_uninstall(name, False, msg)
        return f"uninstall failed: {msg}"

    lines = [
        f"uninstalled: {name}",
        f"  {msg}",
    ]
    if tbl_msg:
        lines.append(f"  {tbl_msg}")
    lines += [
        "",
        "  pip dependencies not removed (may be shared by other packages).",
        "  if confirmed no longer needed, clean up manually:",
        f"    {Path(os.environ.get('TEXT_CLI_HOME', str(Path.home() / 'text-cli'))) / 'service' / '.venv' / 'bin' / 'pip'} uninstall <pkg>",
    ]

    result = "\n".join(lines)
    log_uninstall(name, True, "uninstalled")
    # Refresh MCP routing if an MCP package was removed
    if _was_mcp:
        try:
            from core.mcp_dispatch import refresh_routes
            refresh_routes()
        except Exception as e:
            logger.debug("Failed to refresh MCP routes during uninstall of '%s': %s", name, e)
            pass
    try:
        manifest_remove(name)
        _remove_handler_init(name)
    except Exception as e:
        logger.debug("Failed to remove manifest/init for '%s': %s", name, e)
        pass

    # Purge module references from sys.modules
    try:
        from .text_cli_install import _invalidate_package
        _invalidate_package(name)
    except Exception as e:
        logger.debug("Failed to invalidate package modules for '%s': %s", name, e)

    return result


def _remove_handler_init(pkg_name: str):
    """Remove an entry from handler_inits.py using safe_name fuzzy match."""
    try:
        content = _INITS_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return

    safe = pkg_name.replace("-", "_")
    lines = content.split('\n')
    new_lines = [l for l in lines if safe not in l]
    if len(new_lines) != len(lines):
        _INITS_PATH.write_text('\n'.join(new_lines), encoding="utf-8")
