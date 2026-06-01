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

import os

from core.registry import directive

from .installer.validate import SYSTEM_DOMAINS
from .installer.filesystem import remove_files
from .installer.dependencies import check_deps_shared
from .installer.audit import log_uninstall
from .package_manifest import remove as manifest_remove
from pathlib import Path

_INITS_PATH = Path(__file__).resolve().parent.parent / "config" / "handler_inits.py"

@directive("text-cli", "uninstall", domain_alias="文本指令", action_aliases={"uninstall": "卸载"})
def text_cli_uninstall(params: list[str]) -> str:
    """Uninstall an instruction package by name."""
    if not params:
        return "用法: AI:text-cli;uninstall,<包名>\n\n" \
               "使用 AI:text-cli;query 查看已安装的包。"

    name = params[0].strip()

    # 1. System domain protection
    if name in SYSTEM_DOMAINS:
        log_uninstall(name, False, f"rejected: system domain")
        return f"\"{name}\" 是系统保留域，不可卸载。"

    # 2. Remove files
    ok, msg = remove_files(name)
    if not ok:
        log_uninstall(name, False, msg)
        return f"卸载失败: {msg}"

    # 2.5 Drop tables (schema.tables → DROP TABLE)
    from pathlib import Path
    from .installer.filesystem import _drop_tables
    safe = name.replace("-", "_")
    schema_path = Path(__file__).resolve().parent / "schema" / f"{safe}_schema.json"
    tbl_msg = ""
    try:
        ok_tbl, tbl_msg = _drop_tables(schema_path, name)
    except Exception:
        pass

    # 3. Build result
    lines = [
        f"已卸载: {name}",
        f"  {msg}",
    ]
    if tbl_msg:
        lines.append(f"  {tbl_msg}")
    lines += [
        "",
        "  pip 依赖未移除（可能被其他包共用）。",
        "  如确认不再需要，手动清理:",
        f"    {Path(os.environ.get('TEXT_CLI_HOME', str(Path.home() / 'text-cli'))) / 'service' / '.venv' / 'bin' / 'pip'} uninstall <pkg>",
    ]

    result = "\n".join(lines)
    log_uninstall(name, True, "uninstalled")
    try:
        manifest_remove(name)
        _remove_handler_init(name)
    except Exception:
        pass
    return result


def _remove_handler_init(pkg_name: str):
    """Remove an entry from handler_inits.py."""
    try:
        content = _INITS_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return

    mod_path = f"handlers.{pkg_name}_handler"
    lines = content.split('\n')
    new_lines = [l for l in lines if mod_path not in l]
    if len(new_lines) != len(lines):
        _INITS_PATH.write_text('\n'.join(new_lines), encoding="utf-8")
