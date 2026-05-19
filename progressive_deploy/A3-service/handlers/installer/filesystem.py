"""File operations for package install/uninstall."""

from __future__ import annotations

import pathlib
import shutil

HANDLERS_DIR = pathlib.Path(__file__).parent.parent
SCHEMA_DIR = HANDLERS_DIR / "schema"
# Shared directory for cmd runtime whitelists (copilot reads from here)
COPILOT_WHITELIST_DIR = pathlib.Path(__file__).parent.parent.parent / "copilot" / "whitelists"


def install_files(name: str, meta: dict, runtime: str = "python", force: bool = False) -> tuple[bool, str]:
    """Copy handler.py (if applicable) and schema.json into the service dirs.

    For MCP packages, only schema.json is copied (no local handler).

    Returns (ok, message).
    """
    HANDLERS_DIR.mkdir(parents=True, exist_ok=True)
    SCHEMA_DIR.mkdir(parents=True, exist_ok=True)

    schema_src = pathlib.Path(meta["schema_path"])
    schema_dst = SCHEMA_DIR / f"{name}_schema.json"

    # Check existing
    if schema_dst.exists() and not force:
        # Check handler too for python packages
        handler_dst = HANDLERS_DIR / f"{name}.py"
        if not handler_dst.exists() and runtime == "python":
            pass  # handler missing but schema exists — install anyway
        elif handler_dst.exists() and runtime == "python":
            return False, f"包 \"{name}\" 已安装。使用 AI:text-cli;install,{name},--force 强制覆盖"
        elif runtime == "mcp" and schema_dst.exists():
            return False, f"包 \"{name}\" 已安装。使用 AI:text-cli;install,{name},--force 强制覆盖"

    try:
        shutil.copy2(schema_src, schema_dst)
    except OSError as e:
        return False, f"File copy failed: {e}"

    # Copy handler only for Python packages
    if runtime == "python":
        handler_src = pathlib.Path(meta["handler_path"])
        handler_dst = HANDLERS_DIR / f"{name}.py"
        try:
            shutil.copy2(handler_src, handler_dst)
        except OSError as e:
            return False, f"handler 复制失败: {e}"
        return True, f"File deployment complete: {name}.py + {name}_schema.json"

    elif runtime == "mcp":
        return True, f"MCP schema registered: {name}_schema.json"

    elif runtime == "node":
        # JS package: copy handler.js + schema.json
        handler_src = pathlib.Path(meta["handler_path"])
        handler_dst = HANDLERS_DIR / f"{name}.js"
        if handler_dst.exists() and not force:
            return False, f"包 \"{name}\" 已安装。使用 AI:text-cli;install,{name},--force 强制覆盖"
        try:
            shutil.copy2(handler_src, handler_dst)
            shutil.copy2(schema_src, schema_dst)
        except OSError as e:
            return False, f"File copy failed: {e}"
        return True, f"File deployment complete: {name}.js + {name}_schema.json"

    elif runtime == "cmd":
        # cmd package: schema → service discovery, whitelist → copilot execution dir
        COPILOT_WHITELIST_DIR.mkdir(parents=True, exist_ok=True)
        wl_src = pathlib.Path(meta["whitelist_path"])
        wl_dst = COPILOT_WHITELIST_DIR / f"{name}_whitelist.json"
        try:
            shutil.copy2(schema_src, schema_dst)
            shutil.copy2(wl_src, wl_dst)
        except OSError as e:
            return False, f"File copy failed: {e}"
        return True, f"File deployment complete: {name}_schema.json + whitelists/{name}_whitelist.json"

    return True, "File deployment complete"


def remove_files(name: str) -> tuple[bool, str]:
    """Remove handler.py and schema.json for a package.

    Returns (ok, message).
    """
    handler_path = HANDLERS_DIR / f"{name}.py"
    schema_path = SCHEMA_DIR / f"{name}_schema.json"

    removed = []

    if handler_path.exists():
        handler_path.unlink()
        removed.append(f"handlers/{name}.py")

    if schema_path.exists():
        schema_path.unlink()
        removed.append(f"handlers/schema/{name}_schema.json")

    if not removed:
        return False, f"包 \"{name}\" not installed"

    return True, "Removed: " + ", ".join(removed)
