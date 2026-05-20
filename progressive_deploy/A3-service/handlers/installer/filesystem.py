"""File operations for package install/uninstall."""

from __future__ import annotations

import os
import pathlib
import shutil

_PROJECT = pathlib.Path(os.environ.get("TEXT_CLI_HOME", str(pathlib.Path.home() / "text-cli")))
HANDLERS_DIR = _PROJECT / "service" / "handlers"
SCHEMA_DIR = HANDLERS_DIR / "schema"
COPILOT_WHITELIST_DIR = _PROJECT / "copilot" / "whitelists"


def _safe_name(name: str) -> str:
    return name.replace("-", "_")


def install_files(name: str, meta: dict, runtime: str = "python", force: bool = False) -> tuple[bool, str]:
    """Copy handler.py (if applicable) and schema.json into the service dirs.

    For MCP packages, only schema.json is copied (no local handler).

    Returns (ok, message).
    """
    HANDLERS_DIR.mkdir(parents=True, exist_ok=True)
    SCHEMA_DIR.mkdir(parents=True, exist_ok=True)

    safe = _safe_name(name)
    schema_src = pathlib.Path(meta["schema_path"])
    schema_dst = SCHEMA_DIR / f"{safe}_schema.json"

    # Check existing
    if schema_dst.exists() and not force:
        handler_dst = HANDLERS_DIR / f"{safe}.py"
        if not handler_dst.exists() and runtime == "python":
            pass
        elif handler_dst.exists() and runtime == "python":
            return False, f"包 \"{name}\" 已安装。使用 AI:text-cli;install,{name},--force 强制覆盖"
        elif runtime == "mcp" and schema_dst.exists():
            return False, f"包 \"{name}\" 已安装。使用 AI:text-cli;install,{name},--force 强制覆盖"

    try:
        shutil.copy2(schema_src, schema_dst)
    except OSError as e:
        return False, f"文件复制失败: {e}"

    # Copy handler only for Python packages
    if runtime == "python":
        handler_src = pathlib.Path(meta["handler_path"])
        handler_dst = HANDLERS_DIR / f"{safe}.py"
        try:
            shutil.copy2(handler_src, handler_dst)
        except OSError as e:
            return False, f"handler 复制失败: {e}"
        return True, f"文件部署完成: {safe}.py + {safe}_schema.json"

    elif runtime == "mcp":
        return True, f"MCP schema 注册完成: {safe}_schema.json"

    elif runtime == "node":
        # JS package: copy handler.js + schema.json
        handler_src = pathlib.Path(meta["handler_path"])
        handler_dst = HANDLERS_DIR / f"{safe}.js"
        if handler_dst.exists() and not force:
            return False, f"包 \"{name}\" 已安装。使用 AI:text-cli;install,{name},--force 强制覆盖"
        try:
            shutil.copy2(handler_src, handler_dst)
            shutil.copy2(schema_src, schema_dst)
        except OSError as e:
            return False, f"文件复制失败: {e}"
        return True, f"文件部署完成: {safe}.js + {safe}_schema.json"

    elif runtime == "cmd":
        # cmd package: schema → service discovery, whitelist → copilot execution dir
        COPILOT_WHITELIST_DIR.mkdir(parents=True, exist_ok=True)
        wl_src = pathlib.Path(meta["whitelist_path"])
        wl_dst = COPILOT_WHITELIST_DIR / f"{safe}_whitelist.json"
        try:
            shutil.copy2(schema_src, schema_dst)
            shutil.copy2(wl_src, wl_dst)
        except OSError as e:
            return False, f"文件复制失败: {e}"
        return True, f"文件部署完成: {safe}_schema.json + whitelists/{safe}_whitelist.json"

    return True, "文件部署完成"


def remove_files(name: str) -> tuple[bool, str]:
    """Remove handler.py and schema.json for a package.

    Returns (ok, message).
    """
    safe = _safe_name(name)
    handler_path = HANDLERS_DIR / f"{safe}.py"
    schema_path = SCHEMA_DIR / f"{safe}_schema.json"

    removed = []

    if handler_path.exists():
        handler_path.unlink()
        removed.append(f"handlers/{safe}.py")

    if schema_path.exists():
        schema_path.unlink()
        removed.append(f"handlers/schema/{safe}_schema.json")

    if not removed:
        return False, f"包 \"{name}\" 未安装"

    return True, "已移除: " + ", ".join(removed)
