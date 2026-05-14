"""
text-cli;uninstall — Platform self-management: uninstall instruction package。

Remove handler.py + schema.json, retain audit log。
Protected system domain (text-cli) cannot be uninstalled。

Directives:
    AI:text-cli;uninstall,<包名>     → Uninstall specified package
    AI:文本指令;卸载,<包名>           → 中文别名

Author: Tide 🌊
"""

from __future__ import annotations

from core.registry import directive

from .installer.validate import SYSTEM_DOMAINS
from .installer.filesystem import remove_files
from .installer.dependencies import check_deps_shared
from .installer.audit import log_uninstall


@directive("text-cli", "uninstall")
@directive("文本指令", "卸载")
def text_cli_uninstall(params: list[str]) -> str:
    """Uninstall an instruction package by name."""
    if not params:
        return "用法: AI:text-cli;uninstall,<包名>\n\n" \
               "Use AI:text-cli;query to see installed packages。"

    name = params[0].strip()

    # 1. System domain protection
    if name in SYSTEM_DOMAINS:
        log_uninstall(name, False, f"rejected: system domain")
        return f"\"{name}\" is a system domain and cannot be uninstalled。"

    # 2. Remove files
    ok, msg = remove_files(name)
    if not ok:
        log_uninstall(name, False, msg)
        return f"Uninstall failed: {msg}"

    # 3. Build result
    lines = [
        f"Uninstalled: {name}",
        f"  {msg}",
        "",
        "  pip dependencies not removed (may be shared by other packages)。",
        "  If confirmed unused, clean up manually:",
        f"    /path/to/text-cli/service/.venv/bin/pip uninstall <pkg>",
    ]

    result = "\n".join(lines)
    log_uninstall(name, True, "uninstalled")
    return result
