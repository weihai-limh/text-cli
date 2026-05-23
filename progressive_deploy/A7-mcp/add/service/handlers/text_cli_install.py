"""
text-cli;install — 平台自管理：安装指令包。

从注册源搜索包 → 验证结构 → 部署文件 → 安装依赖 → 审计记录。
包来源限定为本地 text-cliV1/ 目录，不接受任意 URL。

Directives:
    AI:text-cli;install,<包名>           → 安装指定包
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
from .package_manifest import register as manifest_register

import ast
from pathlib import Path

_INITS_PATH = Path(__file__).resolve().parent.parent / "config" / "handler_inits.py"


def _safe_name(name: str) -> str:
    return name.replace("-", "_")


def _find_init_fn(handler_path: str) -> tuple[str | None, str | None]:
    """Parse init function and infer arg_key from parameter names.

    Returns (fn_name, arg_key) where arg_key is one of:
        "project_root", "db", "db_dict", "quota", None
    """
    _ARG_KEY_MAP = {"project_root": "project_root", "db_path": "db",
                     "db_file": "quota", "db_dict": "db_dict"}
    try:
        with open(handler_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("init_"):
                fn_name = node.name
                for arg in node.args.args:
                    if arg.arg in _ARG_KEY_MAP:
                        return fn_name, _ARG_KEY_MAP[arg.arg]
                # 有参数但不在映射表中，回退为None
                if node.args.args:
                    return fn_name, None
                # 无参数
                return fn_name, None
    except Exception:
        pass
    return None, None


@directive("text-cli", "install")
@directive("文本指令", "安装")
def text_cli_install(params: list[str]) -> str:
    """Install an instruction package by name."""
    if not params:
        return "用法: AI:text-cli;install,<包名>\n\n" \
               "使用 AI:text-cli;query,category 查看可用分类。"

    name = params[0].strip()
    force = len(params) > 1 and params[1].strip() == "--force"

    # 1. Validate
    ok, msg, meta = validate_package(name)
    if not ok:
        log_install(name, {}, False, msg)
        return msg if msg.startswith("安装失败") else f"安装失败: {msg}"

    schema = meta["schema"]

    # 2. Install files
    runtime = schema.get("runtime", "python")
    ok, msg = install_files(name, meta, runtime=runtime, force=force)
    if not ok:
        log_install(name, meta, False, msg)
        return msg if msg.startswith("安装失败") else f"安装失败: {msg}"

    # 3. Check required secrets
    secrets_warnings = _check_secrets(schema, skip_check="--skip-secrets-check" in params)

    # 4. Install dependencies (Python only)
    if runtime == "python":
        requires = schema.get("requires", {})
        ok_deps, dep_msg = install_deps(meta.get("req_path"), name, requires=requires)
    else:
        ok_deps, dep_msg = True, "无 pip 依赖"

    # 4. Format result
    directives = schema.get("directives", [])
    mcp_server = schema.get("mcp_server", "")
    lines = [
        f"安装完成: {name} ({schema.get('name_cn', '')})",
        f"  runtime: {runtime}",
    ]
    if mcp_server:
        lines.append(f"  MCP server: {mcp_server}")
    lines += [
        f"  {dep_msg}",
        "",
        f"  {len(directives)} 条指令:",
    ]
    for d in directives:
        usage = d.get("usage", f"{d.get('domain','')};{d.get('action','')}")
        usage_en = d.get("usage_en", "")
        lines.append(f"    {usage}")
        if usage_en and usage_en != usage:
            lines.append(f"      {usage_en}")

    if not ok_deps:
        lines.append("")
        lines.append(f"  ⚠ pip 依赖安装失败: {dep_msg}")
        lines.append("    指令已部署，但可能因缺少依赖而无法执行。")
        lines.append(f"    手动安装: {meta.get('req_path', 'N/A')}")

    result = "\n".join(lines)

    if msg and "\n" in msg:
        extra = "\n".join(msg.split("\n")[1:])
        if extra.strip():
            result += f"\n{extra}"

    # Append secrets warnings
    if secrets_warnings:
        result += "\n\n" + secrets_warnings

    log_install(name, meta, True, "installed")

    # Write manifest for export tracking
    try:
        safe = _safe_name(name)
        pkg_source = str(meta["path"])
        pkg_domain = schema.get("directives", [{}])[0].get("domain", name)
        pkg_type = schema.get("type", "native")
        manifest_register(
            name, pkg_domain, pkg_type, pkg_source,
            files={
                "handler": f"packages/{name}/handler.py",
                "schema": f"handlers/schema/{safe}_schema.json",
            },
            directives=[f"{d.get('domain',name)};{d.get('action','')}" for d in schema.get("directives", [])]
        )

        init_fn, arg_key = _find_init_fn(meta.get("handler_path", ""))
        if init_fn is None:
            init_fn = f"init_{safe}_handler"
        _append_handler_init(f"packages.{name}.handler", init_fn, arg_key)
    except Exception:
        pass  # manifest/init optional, don't block install

    return result


def _append_handler_init(mod_path: str, fn_name: str, arg_key: str = None):
    """Append an entry to handler_inits.py for auto-load on restart."""
    import re
    try:
        content = _INITS_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return

    entry_pattern = f'("{mod_path}", "{fn_name}"'
    if entry_pattern in content:
        return

    arg_key_str = '"' + (arg_key or "None") + '"'
    new_entry = f'    ("{mod_path}", "{fn_name}", {arg_key_str}, None),\n'

    handler_start = content.find("HANDLER_INITS = [")
    if handler_start < 0:
        return

    rest = content[handler_start:]
    m = re.search(r'\n\]', rest)
    if m:
        insert_pos = handler_start + m.start() + 1
        content = content[:insert_pos] + "\n" + new_entry + content[insert_pos:]
        _INITS_PATH.write_text(content, encoding="utf-8")


def _check_secrets(schema: dict, skip_check: bool = False) -> str:
    """Check that required secrets are registered in key_registry.

    Returns a warning string if secrets are missing, empty string otherwise.
    """
    if skip_check:
        return ""

    secrets = schema.get("requires", {}).get("secrets", [])
    if not secrets:
        return ""

    # Try to access key_registry
    missing = []
    try:
        from text_cli_modules.key.key_registry import get as key_get
        # We need DB_PATH — try common locations
        import os
        db_path = os.environ.get("TEXT_CLI_DB", str(Path(os.environ.get("TEXT_CLI_HOME", str(Path.home() / "text-cli"))) / "service" / "text_cli.db"))
        for secret_name in secrets:
            val = key_get({"config": db_path}, secret_name)
            if not val:
                missing.append(secret_name)
    except ImportError:
        # key_registry not available — all secrets missing
        missing = list(secrets)
    except Exception:
        missing = list(secrets)

    if not missing:
        return ""

    lines = [
        "⚠ 缺少所需凭据:",
    ]
    for s in missing:
        lines.append(f"  • {s} — 使用 AI:key;register,{s},<值>,api_key 注册")
    lines.append("")
    lines.append("  跳过检查: AI:text-cli;install,<包名>,--skip-secrets-check")
    return "\n".join(lines)
