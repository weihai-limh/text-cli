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

    # Check existing (schema-based, handler lives in packages/ now)
    if schema_dst.exists() and not force:
        if runtime in ("python", "mcp"):
            return False, f"包 \"{name}\" 已安装。使用 AI:text-cli;install,{name},--force 强制覆盖"

    try:
        shutil.copy2(schema_src, schema_dst)
    except OSError as e:
        return False, f"文件复制失败: {e}"

    # Copy handler only for Python packages
    lines = []
    pkg_dir = pathlib.Path(meta.get("path", ""))
    if runtime == "python":
        # handler.py stays in packages/<name>/ — no copy to handlers/
        lines.append(f"文件部署完成: packages/{name}/handler.py + {name}_schema.json")

    elif runtime == "mcp":
        lines.append(f"MCP schema 注册完成: {name}_schema.json")

    elif runtime == "node":
        handler_src = pathlib.Path(meta["handler_path"])
        handler_dst = HANDLERS_DIR / f"{safe}.js"
        if handler_dst.exists() and not force:
            return False, f"包 \"{name}\" 已安装。使用 AI:text-cli;install,{name},--force 强制覆盖"
        try:
            shutil.copy2(handler_src, handler_dst)
            shutil.copy2(schema_src, schema_dst)
        except OSError as e:
            return False, f"文件复制失败: {e}"
        lines.append(f"文件部署完成: {name}.js + {name}_schema.json")

    elif runtime == "cmd":
        COPILOT_WHITELIST_DIR.mkdir(parents=True, exist_ok=True)
        wl_src = pathlib.Path(meta["whitelist_path"])
        wl_dst = COPILOT_WHITELIST_DIR / f"{safe}_whitelist.json"
        try:
            shutil.copy2(schema_src, schema_dst)
            shutil.copy2(wl_src, wl_dst)
        except OSError as e:
            return False, f"文件复制失败: {e}"
        lines.append(f"文件部署完成: {name}_schema.json + whitelists/{name}_whitelist.json")

    elif runtime == "path":
        # Path packages: deploy path/ and knowledge/ directories (zero-knowledge)
        _deploy_path_resources(pkg_dir, name, lines)

    elif runtime == "aggregate":
        # Aggregate packages: deploy route table JSON to A8-discovery/aggregate/
        _deploy_aggregate_resources(pkg_dir, name, lines)

    else:
        lines.append("文件部署完成")

    # Deploy runtime modules (text_cli_modules/)
    if pkg_dir.is_dir():
        ok_mod, mod_msg = _deploy_runtime_modules(pkg_dir, name)
        if mod_msg:
            lines.append(mod_msg)

        # Deploy auxiliary files
        ok_aux, aux_msg = _deploy_aux_files(pkg_dir, name, runtime)
        if aux_msg:
            lines.append(aux_msg)

        # Deploy package config (config/* → service/config/, skip existing)
        ok_cfg, cfg_msg = _deploy_package_config(pkg_dir, name)
        if cfg_msg:
            lines.append(cfg_msg)

        # Check binaries
        ok_bin, bin_msg = _check_binary(pkg_dir, meta)
        if bin_msg:
            lines.append(bin_msg)

    return True, "\n".join(lines)


def _deploy_runtime_modules(pkg_dir: pathlib.Path, name: str) -> tuple[bool, str]:
    """Deploy package's text_cli_modules/ runtime dependencies to service."""
    modules_src = pkg_dir / "text_cli_modules"
    if not modules_src.is_dir():
        return True, ""

    modules_dst = _PROJECT / "service" / "text_cli_modules"
    modules_dst.mkdir(parents=True, exist_ok=True)

    copied = []
    for item in modules_src.rglob("*"):
        if item.name.startswith("__pycache__"):
            continue
        rel = item.relative_to(modules_src)
        dst = modules_dst / rel
        if item.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(item), str(dst))
        copied.append(str(rel))

    if copied:
        return True, f"  runtime modules: {', '.join(copied)}"
    return True, ""


def _deploy_aux_files(pkg_dir: pathlib.Path, name: str, runtime: str) -> tuple[bool, str]:
    """Deploy auxiliary files (binaries, JS files with non-standard names)."""
    pkg_dir = pathlib.Path(pkg_dir)
    extra = []

    if runtime == "node":
        for js_file in sorted(pkg_dir.glob("*.js")):
            handler_name = f"{name}.js"
            if js_file.name != handler_name:
                dst = HANDLERS_DIR / js_file.name
                shutil.copy2(str(js_file), str(dst))
                extra.append(js_file.name)

    if runtime == "python":
        for py_file in sorted(pkg_dir.glob("*.py")):
            if py_file.name != "handler.py":
                dst = HANDLERS_DIR / py_file.name
                shutil.copy2(str(py_file), str(dst))
                extra.append(py_file.name)

    if extra:
        return True, f"  auxiliary: {', '.join(extra)}"
    return True, ""


def _deploy_package_config(pkg_dir: pathlib.Path, name: str) -> tuple[bool, str]:
    """Deploy package's config/ directory to service/config/.

    Files already present in the target directory are skipped (never overwritten).
    Subdirectories are not recursed — only top-level files are copied.
    """
    config_src = pathlib.Path(pkg_dir) / "config"
    if not config_src.is_dir():
        return True, ""

    config_dst = _PROJECT / "service" / "config"
    config_dst.mkdir(parents=True, exist_ok=True)

    copied = []
    skipped = []
    for item in sorted(config_src.iterdir()):
        if item.is_dir():
            continue
        dst = config_dst / item.name
        if dst.exists():
            skipped.append(item.name)
            continue
        shutil.copy2(str(item), str(dst))
        copied.append(item.name)

    parts = []
    if copied:
        parts.append(f"config: {', '.join(copied)}")
    if skipped:
        parts.append(f"config skipped: {', '.join(skipped)}")
    if parts:
        return True, "  " + " | ".join(parts)
    return True, ""


def _deploy_path_resources(pkg_dir: pathlib.Path, name: str, lines: list[str]) -> None:
    """Deploy path/ and knowledge/ directories for runtime=path packages.

    path/*.json   → service/paths/<pkg_id>/
    knowledge/*   → service/knowledge/<pkg_id>/
    """
    pkg_dir = pathlib.Path(pkg_dir)
    path_src = pkg_dir / "path"
    knowledge_src = pkg_dir / "knowledge"

    deployed = []

    if path_src.is_dir():
        dst = _PROJECT / "service" / "paths" / name
        dst.mkdir(parents=True, exist_ok=True)
        for item in sorted(path_src.iterdir()):
            if item.is_file():
                if not (dst / item.name).exists():
                    shutil.copy2(str(item), str(dst / item.name))
                    deployed.append(f"path/{item.name}")

    if knowledge_src.is_dir():
        dst = _PROJECT / "service" / "knowledge" / name
        dst.mkdir(parents=True, exist_ok=True)
        for item in sorted(knowledge_src.rglob("*")):
            if item.is_file():
                rel = item.relative_to(knowledge_src)
                dest = dst / rel
                if not dest.exists():
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(item), str(dest))
                    deployed.append(f"knowledge/{rel}")

    lines.append(f"文件部署完成: {name}_schema.json")
    if deployed:
        lines.append(f"  path resources: {', '.join(deployed)}")


def _deploy_aggregate_resources(pkg_dir: pathlib.Path, name: str, lines: list[str]) -> None:
    """Deploy aggregate route-table JSON for runtime=aggregate packages.

    *.json (route tables) → A8-discovery/aggregate/
    """
    pkg_dir = pathlib.Path(pkg_dir)
    agg_dst = _PROJECT.parent / "A8-discovery" / "aggregate"
    agg_dst.mkdir(parents=True, exist_ok=True)

    deployed = []
    for item in sorted(pkg_dir.glob("*.json")):
        if item.name == "schema.json":
            continue
        dst = agg_dst / item.name
        if not dst.exists():
            shutil.copy2(str(item), str(dst))
            deployed.append(item.name)

    lines.append(f"aggregate 部署完成: {name}_schema.json")
    if deployed:
        lines.append(f"  route tables: {', '.join(deployed)}")


def _check_binary(pkg_dir: pathlib.Path, meta: dict) -> tuple[bool, str]:
    """Check binary dependencies declared in schema.requires.binary."""
    import stat
    schema = meta.get("schema", {})
    requires = schema.get("requires", {})
    binaries = requires.get("binary", {})
    if not binaries:
        return True, ""

    warnings = []
    for bin_name, bin_info in binaries.items():
        bin_path = pkg_dir / bin_name
        if not bin_path.is_file():
            warnings.append(f"{bin_name}: 未找到")
            continue
        if not (bin_path.stat().st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)):
            warnings.append(f"{bin_name}: 不可执行")

    if warnings:
        return True, f"  ⚠ binary: {'; '.join(warnings)}"
    return True, "  ✓ binaries ok"


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
