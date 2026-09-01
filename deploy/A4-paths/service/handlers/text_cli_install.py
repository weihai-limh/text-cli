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

import ast
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

from core.registry import directive

from .installer.audit import log_install
from .installer.dependencies import install_deps, install_npm_deps
from .installer.filesystem import install_files
from .installer.validate import validate_package
from .package_manifest import register as manifest_register

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
    if not handler_path:
        return None, None
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
    except Exception as e:
        logger.debug("Failed to scan handler.py for directive fn: %s", e)
        pass
    return None, None


def _invalidate_package(name: str):
    """Invalidate an installed package: unregister directives + purge from sys.modules.

    Called before re-import on update, and after file removal on uninstall.
    """
    import sys
    from core.registry import unregister as _registry_unregister

    # 1. Unregister directives from _registry
    safe = name.replace("-", "_")
    schema_path = Path(__file__).resolve().parent / "schema" / f"{safe}_schema.json"
    if schema_path.is_file():
        try:
            import json as _json
            schema_data = _json.loads(schema_path.read_text(encoding="utf-8"))
            for d in schema_data.get("directives", []):
                _registry_unregister(d.get("domain", name), d.get("action", ""))
        except Exception as e:
            logger.debug("Failed to unregister directives for '%s': %s", name, e)
    else:
        logger.debug("Schema file not found for '%s', skipping directive unregister", name)

    # 2. Purge module references from sys.modules (recursive for submodules)
    pkg_prefix = f"packages.{name}."
    for mod_name in list(sys.modules.keys()):
        if mod_name == f"packages.{name}" or mod_name.startswith(pkg_prefix):
            del sys.modules[mod_name]
            logger.debug("Purged module from sys.modules: %s", mod_name)


def _load_and_wire(name: str, safe: str, init_fn_name: str, arg_key: str | None):
    """Import a package handler fresh and wire init + dispatch. No reload.

    For new installs: module is not yet in sys.modules, direct import_module.
    For updates: caller should call _invalidate_package() first, then this function.
    Mirrors the startup init logic in main.py (HANDLER_INITS + DISPATCH_INJECTS).
    """
    import importlib
    import os

    from . import degraded as _degraded

    mod_path = f"packages.{name}.handler"
    try:
        mod = importlib.import_module(mod_path)
    except Exception as e:
        logger.warning("Import failed for %s: %s (will need restart)", mod_path, e)
        if name not in _degraded:
            _degraded.append(name)
        return
    if name in _degraded:
        _degraded.remove(name)

    # Resolve init argument (mirrors main.py _ARG_MAP)
    from pathlib import Path
    home = Path(os.environ.get("TEXT_CLI_HOME",
                               str(Path.home() / "text-cli")))          # 服务根
    service_dir = home / "service"                                       # service 目录
    sqlite_dir = home / "service" / "text_cli_modules" / "sqlite"
    sqlite_db = str(sqlite_dir / "token_registry.db")
    _arg_values = {
        "db": sqlite_db,
        "quota": str(sqlite_dir / "quota.db"),
        "db_dict": {"config": sqlite_db},
        "project_root": str(service_dir),                                # 与 main.py 启动 init 一致
    }

    # Call init function
    try:
        init_fn = getattr(mod, init_fn_name, None)
        if init_fn and callable(init_fn):
            if arg_key and arg_key in _arg_values:
                init_fn(_arg_values[arg_key])
            else:
                init_fn()
    except Exception as e:
        logger.warning("Load-and-wire init failed for %s.%s: %s", mod_path, init_fn_name, e)

    # Re-inject dispatch callbacks for key / task-manager handlers
    try:
        from main import _internal_dispatch
        for setter_name in ("_set_dispatch", "_set_task_dispatch"):
            setter = getattr(mod, setter_name, None)
            if setter and callable(setter):
                setter(_internal_dispatch)
    except Exception as e:
        logger.debug("Load-and-wire dispatch inject skipped for %s: %s", mod_path, e)

    logger.info("Loaded handler: %s (no restart needed)", mod_path)


@directive("text-cli", "install", domain_alias="文本指令", action_aliases={"install": "安装"})
def text_cli_install(params: list[str]) -> dict:
    """Install an instruction package by name."""
    if not params:
        return {"status": "error", "reason": "usage: AI:text-cli;install,<package>\n\nUse AI:text-cli;query,category to view available categories."}

    name = params[0].strip()
    force = len(params) > 1 and params[1].strip() == "--force"

    # 1. Validate
    ok, msg, meta = validate_package(name)
    if not ok:
        log_install(name, {}, False, msg)
        return {"status": "error", "reason": msg}

    schema = meta["schema"]

    # 2. Install files
    runtime = schema.get("runtime", "python")
    ok, msg = install_files(name, meta, runtime=runtime, force=force)
    if not ok:
        log_install(name, meta, False, msg)
        return {"status": "error", "reason": msg}

    # 3. Check required secrets
    secrets_warnings = _check_secrets(schema, skip_check="--skip-secrets-check" in params)

    # 4. Install dependencies
    # pip 与 npm 分别装（两个独立 if——python+js 双环境包两者都要执行）
    requires = schema.get("requires", {})
    entry_runtimes = meta.get("entry_runtimes", [])
    ok_deps, dep_msg = True, "no dependencies"
    if runtime == "python" or "python" in entry_runtimes:
        ok_pip, pip_msg = install_deps(meta.get("req_path"), name, requires=requires)
        ok_deps, dep_msg = ok_pip, pip_msg
    if runtime == "js" or "js" in entry_runtimes:
        npm_dir = meta.get("npm_dir")
        if npm_dir:
            ok_npm, npm_msg = install_npm_deps(npm_dir)
            ok_deps = ok_deps and ok_npm
            dep_msg = dep_msg if ok_npm else npm_msg
        elif not ok_deps:
            dep_msg = "no package.json, skip npm"

    # 4. Format result
    directives = schema.get("directives", [])
    mcp_server = schema.get("mcp_server", "")
    lines = [
        f"install complete: {name} ({schema.get('name_zh', '')})",
        f"  runtime: {runtime}",
    ]
    if mcp_server:
        lines.append(f"  MCP server: {mcp_server}")
    lines += [
        f"  {dep_msg}",
        "",
        f"  {len(directives)} directives:",
    ]
    for d in directives:
        usage = d.get("usage", f"{d.get('domain','')};{d.get('action','')}")
        usage_en = d.get("usage_en", "")
        lines.append(f"    {usage}")
        if usage_en and usage_en != usage:
            lines.append(f"      {usage_en}")

    if not ok_deps:
        lines.append("")
        lines.append(f"  [WARN] dependency install failed: {dep_msg}")
        lines.append("    directive deployed, but may fail to execute due to missing dependencies.")

    # Build result dict
    result_data = {
        "status": "ok",
        "package": name,
        "name_zh": schema.get("name_zh", ""),
        "runtime": runtime,
        "directives": directives,
        "mcp_server": mcp_server,
    }
    if not ok_deps:
        result_data["dep_warning"] = dep_msg

    if msg and "\n" in msg:
        extra = "\n".join(msg.split("\n")[1:])
        if extra.strip():
            result_data["note"] = extra

    if secrets_warnings:
        result_data["secrets_warnings"] = secrets_warnings

    log_install(name, meta, True, "installed")

    # Refresh MCP routing if this is an MCP package
    if schema.get("runtime") == "mcp":
        try:
            from core.mcp_dispatch import refresh_routes
            refresh_routes()
        except Exception as e:
            logger.debug("Failed to refresh MCP routes after install: %s", e)
            pass
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

        # Hot-load: make handler available immediately without restart.
        # New install: direct import_module (no reload needed).
        # Update (--force): invalidate old registrations first, then fresh import.
        if runtime == "python":
            if force:
                _invalidate_package(name)
            _load_and_wire(name, safe, init_fn, arg_key)
    except Exception as e:
        logger.debug("Manifest/init optional for '%s': %s", name, e)
        pass  # manifest/init optional, don't block install

    return result_data


def _append_handler_init(mod_path: str, fn_name: str, arg_key: str | None = None):
    """Append an entry to handler_inits.py for auto-load on restart."""
    import re
    try:
        content = _INITS_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return

    arg_key_str = repr(arg_key) if arg_key else 'None'

    # Match existing entry: if found with same arg_key, skip;
    # if found with different arg_key, replace the line.
    entry_pattern = f'("{mod_path}", "{fn_name}"'
    if entry_pattern in content:
        expected = f'("{mod_path}", "{fn_name}", {arg_key_str}, None)'
        if expected in content:
            return
        lines = content.split('\n')
        new_lines = [l for l in lines if entry_pattern not in l]
        content = '\n'.join(new_lines)
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
        # We need DB_PATH — try common locations
        import os

        from text_cli_modules.key.key_registry import get as key_get
        db_path = os.environ.get("TEXT_CLI_DB", str(Path(os.environ.get("TEXT_CLI_HOME", str(Path.home() / "text-cli"))) / "service" / "text_cli.db"))
        for secret_name in secrets:
            val = key_get({"config": db_path}, secret_name)
            if not val:
                missing.append(secret_name)
    except ImportError:
        # key_registry not available — all secrets missing
        missing = list(secrets)
    except Exception as e:
        logger.debug("Secrets check failed for '%s': %s", schema.get("name", "?"), e)
        missing = list(secrets)

    if not missing:
        return ""

    lines = [
        "⚠ missing required credentials:",
    ]
    for s in missing:
        lines.append(f"  • {s} — use AI:key;register,{s},<value>,api_key to register")
    lines.append("")
    lines.append("  skip check: AI:text-cli;install,<package>,--skip-secrets-check")
    return "\n".join(lines)
