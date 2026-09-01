"""File operations for package install/uninstall."""

from __future__ import annotations

import os
import pathlib
import shutil
import subprocess


def _resolve_project_root() -> pathlib.Path:
    """Resolve project root from TEXT_CLI_HOME at call time."""
    return pathlib.Path(os.environ.get("TEXT_CLI_HOME", str(pathlib.Path.home() / "text-cli")))


_PROJECT = _resolve_project_root()
HANDLERS_DIR = _PROJECT / "service" / "handlers"
SCHEMA_DIR = HANDLERS_DIR / "schema"
COPILOT_WHITELIST_DIR = _PROJECT / "copilot" / "whitelists"


def _safe_name(name: str) -> str:
    if ".." in name or name.startswith(("/", "\\")) or ":" in name:
        raise ValueError(f"Invalid package name: {name!r} (path traversal rejected)")
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
    if schema_dst.exists() and not force and runtime in ("python", "mcp"):
            return False, f"package \"{name}\" already installed. Use AI:text-cli;install,{name},--force to force overwrite"

    try:
        shutil.copy2(schema_src, schema_dst)
    except OSError as e:
        return False, f"file copy failed: {e}"

    # Copy handler only for Python packages
    lines = []
    pkg_dir = pathlib.Path(meta.get("path", ""))
    if runtime == "python":
        # Copy handler.py + schema.json to packages/<name>/
        pkg_dst = _PROJECT / "service" / "packages" / name
        pkg_dst.mkdir(parents=True, exist_ok=True)
        if (pkg_dir / "handler.py").is_file():
            shutil.copy2(str(pkg_dir / "handler.py"), str(pkg_dst / "handler.py"))
        shutil.copy2(schema_src, str(pkg_dst / "schema.json"))
        lines.append(f"file deployed: packages/{name}/handler.py + packages/{name}/schema.json")

    elif runtime == "mcp":
        # Copy service-descriptor.json to packages/<name>/ for refresh_routes
        pkg_dst = _PROJECT / "service" / "packages" / name
        pkg_dst.mkdir(parents=True, exist_ok=True)
        sd_src = pkg_dir / "service-descriptor.json"
        if sd_src.is_file():
            shutil.copy2(str(sd_src), str(pkg_dst / "service-descriptor.json"))
        shutil.copy2(schema_src, str(pkg_dst / "schema.json"))
        lines.append(f"MCP package deployed: packages/{name}/ (schema + service-descriptor)")

    elif runtime == "js":
        handler_src = pathlib.Path(meta["handler_path"])
        handler_dst = HANDLERS_DIR / f"{safe}.js"
        if handler_dst.exists() and not force:
            return False, f"package \"{name}\" already installed. Use AI:text-cli;install,{name},--force to force overwrite"
        try:
            shutil.copy2(handler_src, handler_dst)
            shutil.copy2(schema_src, schema_dst)
            # Deploy package.json for npm dependency resolution
            pkg_json_src = handler_src.parent / "package.json"
            if pkg_json_src.is_file():
                shutil.copy2(str(pkg_json_src), str(HANDLERS_DIR / f"{safe}_package.json"))
        except OSError as e:
            return False, f"file copy failed: {e}"
        lines.append(f"file deployed: {name}.js + {name}_schema.json")

    elif runtime == "cmd":
        COPILOT_WHITELIST_DIR.mkdir(parents=True, exist_ok=True)
        wl_src = pathlib.Path(meta["whitelist_path"])
        wl_dst = COPILOT_WHITELIST_DIR / f"{safe}_whitelist.json"
        try:
            shutil.copy2(schema_src, schema_dst)
            shutil.copy2(wl_src, wl_dst)
        except OSError as e:
            return False, f"file copy failed: {e}"
        lines.append(f"file deployed: {name}_schema.json + whitelists/{name}_whitelist.json")

    elif runtime == "path":
        # Path packages: deploy path/ and knowledge/ directories (zero-knowledge)
        _deploy_path_resources(pkg_dir, name, lines)

    elif runtime == "aggregate":
        # Aggregate packages: deploy route table JSON to A8-discovery/aggregate/
        _deploy_aggregate_resources(pkg_dir, name, lines)

    else:
        lines.append("file deployed")

    # Deploy runtime modules (text_cli_modules/)
    if pkg_dir.is_dir():
        _, mod_msg = _deploy_runtime_modules(pkg_dir, name)
        if mod_msg:
            lines.append(mod_msg)

        # Deploy auxiliary files
        _, aux_msg = _deploy_aux_files(pkg_dir, name, runtime, meta.get("entry_runtimes", []))
        if aux_msg:
            lines.append(aux_msg)

        # Deploy package config (config/* → service/config/, skip existing)
        _, cfg_msg = _deploy_package_config(pkg_dir, name)
        if cfg_msg:
            lines.append(cfg_msg)

        # Deploy tables (schema.tables → SQLite CREATE TABLE)
        _, tbl_msg = _deploy_tables(meta.get("schema", {}), name)
        if tbl_msg:
            lines.append(tbl_msg)

        # Check binaries
        _, bin_msg = _check_binary(pkg_dir, meta)
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


def _deploy_aux_files(pkg_dir: pathlib.Path, name: str, runtime: str,
                      entry_runtimes: list | None = None) -> tuple[bool, str]:
    """Deploy auxiliary files (binaries, JS files with non-standard names).

    双环境包（Python 薄壳 + JS 引擎）：runtime=python 且 entry_runtimes 含 "js"
    时，把包内 *.js + package.json 复制到 packages/<name>/，使引擎文件与
    handler.py 同目录（node_modules 就地 npm install 后相对 require 成立）。
    """
    pkg_dir = pathlib.Path(pkg_dir)
    entry_runtimes = entry_runtimes or []
    extra = []

    if runtime == "js":
        for js_file in sorted(pkg_dir.glob("*.js")):
            handler_name = f"{name}.js"
            if js_file.name != handler_name:
                dst = HANDLERS_DIR / js_file.name
                shutil.copy2(str(js_file), str(dst))
                extra.append(js_file.name)

    elif runtime == "python" and "js" in entry_runtimes:
        # 双环境包：JS 引擎文件 + package.json 部署到 packages/<name>/（与 handler.py 同目录）
        pkg_dst = _PROJECT / "service" / "packages" / name
        pkg_dst.mkdir(parents=True, exist_ok=True)
        for js_file in sorted(pkg_dir.glob("*.js")):
            dst = pkg_dst / js_file.name
            shutil.copy2(str(js_file), str(dst))
            extra.append(js_file.name)
        pkg_json = pkg_dir / "package.json"
        if pkg_json.is_file():
            shutil.copy2(str(pkg_json), str(pkg_dst / "package.json"))
            extra.append("package.json")

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
            if item.is_file() and not (dst / item.name).exists():
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

    lines.append(f"file deployed: {name}_schema.json")
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

    lines.append(f"aggregate deployed: {name}_schema.json")
    if deployed:
        lines.append(f"  route tables: {', '.join(deployed)}")


def _check_binary(pkg_dir: pathlib.Path, meta: dict) -> tuple[bool, str]:
    """Check binary dependencies declared in schema.requires.binaries.

    SPEC v1.3 format:
        "binaries": {"<name>": {"source": "system"|"package"|"npm-global", "min_version": "..."}}
    """
    import shutil

    schema = meta.get("schema", {})
    requires = schema.get("requires", {})
    binaries = requires.get("binaries", {})
    if not binaries:
        return True, ""

    warnings = []
    for bin_name, bin_info in binaries.items():
        source = bin_info.get("source", "system")

        if source == "system":
            if not shutil.which(bin_name):
                warnings.append(f"{bin_name}: system not installed")
        elif source == "package":
            bin_path = pkg_dir / bin_name
            if not bin_path.is_file():
                warnings.append(f"{bin_name}: file missing")
            else:
                import stat
                if not (bin_path.stat().st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)):
                    warnings.append(f"{bin_name}: not executable")
        elif source == "npm-global":
            try:
                result = subprocess.run(
                    ["npm", "bin", "-g"], capture_output=True, text=True, timeout=10, check=False,
                )
                if result.returncode != 0:
                    warnings.append(f"{bin_name}: npm global path query failed")
                else:
                    npm_bin = pathlib.Path(result.stdout.strip())
                    if not (npm_bin / bin_name).exists():
                        warnings.append(f"{bin_name}: npm global not installed")
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                warnings.append(f"{bin_name}: npm unavailable, cannot check global install")

    if warnings:
        return True, "  [WARN] binary: " + "; ".join(warnings)
    return True, "  [OK] binaries"


def remove_files(name: str) -> tuple[bool, str]:
    """Remove handler files and packages directory for a package.

    Cleans up packages/<name>/ (current install target),
    legacy handlers/<safe>.py (old install target), and
    text_cli_modules/ runtime modules (declared via requires.modules).

    Uses runtime-resolved project root to support test environments.

    Returns (ok, message).
    """
    import json as _json

    safe = _safe_name(name)
    project = _resolve_project_root()
    pkg_dir = project / "service" / "packages" / name
    handler_path = project / "service" / "handlers" / f"{safe}.py"
    schema_path = project / "service" / "handlers" / "schema" / f"{safe}_schema.json"

    # 收集 text_cli_modules/ 回收目标（在删 schema 前读 requires.modules 声明）
    modules_to_remove: list[str] = []
    try:
        if schema_path.is_file():
            schema_data = _json.loads(schema_path.read_text(encoding="utf-8"))
            declared = schema_data.get("requires", {}).get("modules", [])
            if isinstance(declared, list):
                modules_to_remove = [m for m in declared if isinstance(m, str)]
    except Exception:
        pass
    # 兜底：按包目录名（下划线 safe + 原名）回收，兼容未声明 requires.modules 的包
    modules_to_remove.append(f"text_cli_modules/{safe}")
    modules_to_remove.append(f"text_cli_modules/{name}")

    removed = []

    if pkg_dir.exists():
        shutil.rmtree(pkg_dir)
        removed.append(f"packages/{name}/")

    if handler_path.exists():
        handler_path.unlink()
        removed.append(f"handlers/{safe}.py")

    if schema_path.exists():
        schema_path.unlink()
        removed.append(f"handlers/schema/{safe}_schema.json")

    # 回收 text_cli_modules/ 运行时模块（去重）
    modules_dir = project / "service" / "text_cli_modules"
    seen: set[str] = set()
    for m in modules_to_remove:
        rel = m.removeprefix("text_cli_modules/")
        if not rel or rel in seen:
            continue
        seen.add(rel)
        target = modules_dir / rel
        if target.exists():
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
            removed.append(f"text_cli_modules/{rel}/")

    if not removed:
        return False, f"package \"{name}\" not installed"

    return True, "removed: " + ", ".join(removed)


# ═══ Table management (schema.tables) ═══

def _deploy_tables(schema: dict, name: str) -> tuple[bool, str]:
    """Execute CREATE TABLE IF NOT EXISTS from schema.tables declaration.

    先检查 requires.service_db 中的骨架表是否存在，
    再执行 tables 中声明的建表 SQL。
    """
    requires = schema.get("requires", {})
    tables = schema.get("tables", [])

    if not requires.get("service_db") and not tables:
        return True, ""

    db_path = os.environ.get(
        "TEXT_CLI_SERVICE_DB",
        str(_PROJECT / "service" / "text_cli_modules" / "sqlite" / "service.db")
    )

    try:
        import sqlite3
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # ① 检查 requires.service_db 骨架表存在性
        required_tables = requires.get("service_db", [])
        missing = []
        for tname in required_tables:
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (tname,)
            )
            if not cursor.fetchone():
                missing.append(tname)

        if missing:
            conn.close()
            return False, (
                f"  ⚠ missing A6 skeleton tables: {', '.join(missing)}。"
                f"deploy A6 infrastructure first (token_registry, token_call_logs)"
            )

        # ② 执行应用自建表
        created = []
        for t in tables:
            conn.execute(t["sql"])
            created.append(t["name"])

        conn.commit()
        conn.close()

        parts = []
        if required_tables:
            parts.append(f"service_db: {', '.join(required_tables)} ✓")
        if created:
            parts.append(f"tables: {', '.join(created)}")
        return True, "  " + " | ".join(parts) if parts else ""
    except Exception as e:
        return False, f"  ⚠ table creation failed ({name}): {e}"


def _drop_tables(schema_json_path: pathlib.Path, name: str) -> tuple[bool, str]:
    """DROP TABLE for each table declared in schema.json[\"tables\"].

    Called during uninstall. Table not found = no error.
    """
    try:
        import json
        schema = json.loads(schema_json_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return True, ""

    tables = schema.get("tables", [])
    if not tables:
        return True, ""

    db_path = os.environ.get(
        "TEXT_CLI_SERVICE_DB",
        str(_PROJECT / "service" / "text_cli_modules" / "sqlite" / "service.db")
    )

    try:
        import sqlite3
        conn = sqlite3.connect(db_path)
        for t in tables:
            conn.execute(f"DROP TABLE IF EXISTS {t['name']}")
        conn.commit()
        conn.close()
        return True, f"  tables dropped: {', '.join(t['name'] for t in tables)}"
    except Exception as e:
        return False, f"  ⚠ table drop failed ({name}): {e}"
