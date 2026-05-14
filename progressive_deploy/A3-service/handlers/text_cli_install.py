"""
text-cli;install — Platform self-management: install instruction package。

Search package source → validate structure → deploy files → install deps → audit。
Package source limited to local text-cliV1/ directory。

Directives:
    AI:text-cli;install,<包名>           → Install specified package
    AI:text-cli;install,<包名>,--force   → 强制覆盖已安装的包
    AI:文本指令;安装,<包名>              → 中文别名

Author: Tide 🌊
"""

from __future__ import annotations

from core.registry import directive

from .installer.validate import validate_package
from .installer.filesystem import install_files
from .installer.dependencies import install_deps
from .installer.audit import log_install


@directive("text-cli", "install")
@directive("文本指令", "安装")
def text_cli_install(params: list[str]) -> str:
    """Install an instruction package by name."""
    if not params:
        return "用法: AI:text-cli;install,<包名>\n\n" \
               "Use AI:text-cli;query,category to see available categories。"

    name = params[0].strip()
    force = len(params) > 1 and params[1].strip() == "--force"

    # 1. Validate
    ok, msg, meta = validate_package(name)
    if not ok:
        log_install(name, {}, False, msg)
        return msg if msg.startswith("Install failed") else f"Install failed: {msg}"

    schema = meta["schema"]

    # 2. Install files
    runtime = schema.get("runtime", "python")
    ok, msg = install_files(name, meta, runtime=runtime, force=force)
    if not ok:
        log_install(name, meta, False, msg)
        return msg if msg.startswith("Install failed") else f"Install failed: {msg}"

    # 3. Install dependencies (Python only)
    if runtime == "python":
        ok_deps, dep_msg = install_deps(meta.get("req_path"), name)
    else:
        ok_deps, dep_msg = True, "no pip dependencies"

    # 4. Format result
    directives = schema.get("directives", [])
    mcp_server = schema.get("mcp_server", "")
    lines = [
        f"Install complete: {name} ({schema.get('name_cn', '')})",
        f"  runtime: {runtime}",
    ]
    if mcp_server:
        lines.append(f"  MCP server: {mcp_server}")
    lines += [
        f"  {dep_msg}",
        "",
        f"  {len(directives)} directive(s):",
    ]
    for d in directives:
        usage = d.get("usage", f"{d.get('domain','')};{d.get('action','')}")
        usage_en = d.get("usage_en", "")
        lines.append(f"    {usage}")
        if usage_en and usage_en != usage:
            lines.append(f"      {usage_en}")

    if not ok_deps:
        lines.append("")
        lines.append(f"  ⚠ pip 依赖Install failed: {dep_msg}")
        lines.append("    Directives deployed but may fail due to missing dependencies。")
        lines.append(f"    Manual install: {meta.get('req_path', 'N/A')}")

    result = "\n".join(lines)
    log_install(name, meta, True, "installed")
    return result
