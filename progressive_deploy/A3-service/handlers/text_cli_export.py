"""
text-cli;export + text-cli;packages — package lifecycle: export & list.

Directives:
    text-cli;export,<id>        → export single package to text-cli-package/
    text-cli;export-all         → export all installed packages
    text-cli;packages           → list installed packages with manifest info

Author: Tide 🌊 — 2026-05-17
"""

import json
import logging
import os
import shutil
from pathlib import Path

from core.registry import directive
from .package_manifest import get, list_all, register as manifest_register

logger = logging.getLogger(__name__)

PACKAGE_DIR = Path(os.environ.get("TEXT_CLI_PACKAGE_DIR",
    str(Path(__file__).resolve().parent.parent / "text-cli-package")))
HANDLERS_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = HANDLERS_DIR.parent


@directive("text-cli", "export")
@directive("文本指令", "导出")
def text_cli_export(params: list[str]) -> str:
    """Export a package to text-cli-package/<id>/"""
    if not params:
        return json.dumps({
            "status": "error",
            "reason": "Usage: text-cli;export,<package_id>"
        })

    pkg_id = params[0]
    pkg = get(pkg_id)
    if not pkg:
        return json.dumps({
            "status": "error",
            "reason": f"Package '{pkg_id}' not in manifest. Install it first or use text-cli;register"
        })

    try:
        dest = PACKAGE_DIR / pkg_id
        dest.mkdir(parents=True, exist_ok=True)

        files = pkg.get("files", {})
        pkg_type = pkg.get("type", "native")

        # Copy handler
        handler_rel = files.get("handler", "")
        if handler_rel:
            src = SERVICE_ROOT / handler_rel
            if src.exists():
                shutil.copy2(src, dest / "handler.py")

        # Copy schema if exists
        schema_rel = files.get("schema", "")
        if schema_rel:
            src = SERVICE_ROOT / schema_rel
            if src.exists():
                shutil.copy2(src, dest / "schema.json")

        # Copy requirements
        req_rel = files.get("requirements", "")
        if req_rel:
            src = Path(req_rel) if Path(req_rel).is_absolute() else SERVICE_ROOT / req_rel
            if src.exists():
                shutil.copy2(src, dest / "requirements.txt")

        # Copy knowledge (nocode packages)
        for k_path in files.get("knowledge", []):
            src = Path(k_path) if Path(k_path).is_absolute() else SERVICE_ROOT / k_path
            if src.exists():
                kdest = dest / "knowledge" / src.name
                kdest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, kdest)

        # Copy paths
        for p_path in files.get("paths", []):
            src = Path(p_path) if Path(p_path).is_absolute() else Path(p_path)
            if src.exists():
                pdest = dest / "paths" / src.name
                pdest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, pdest)

        # Copy README
        readme_rel = files.get("readme", "")
        if readme_rel:
            src = Path(readme_rel) if Path(readme_rel).is_absolute() else SERVICE_ROOT / readme_rel
            if src.exists():
                shutil.copy2(src, dest / "README.md")

        return json.dumps({
            "status": "ok",
            "package": pkg_id,
            "type": pkg_type,
            "dest": str(dest),
        }, ensure_ascii=False)

    except Exception as e:
        logger.exception("export failed for %s", pkg_id)
        return json.dumps({"status": "error", "reason": str(e)})


@directive("text-cli", "export-all")
@directive("文本指令", "全部导出")
def text_cli_export_all(params: list[str]) -> str:
    """Export all installed packages."""
    pkgs = list_all()
    if not pkgs:
        return json.dumps({"status": "ok", "exported": 0, "message": "No packages in manifest"})

    exported = []
    for pkg in pkgs:
        pkg_id = pkg["id"]
        result = json.loads(text_cli_export([pkg_id]))
        exported.append({"id": pkg_id, "status": result.get("status", "error")})

    return json.dumps({
        "status": "ok",
        "exported": len([e for e in exported if e["status"] == "ok"]),
        "total": len(exported),
        "dest": str(PACKAGE_DIR),
        "packages": exported,
    }, ensure_ascii=False)


@directive("text-cli", "packages")
@directive("文本指令", "已安装包")
def text_cli_packages(params: list[str]) -> str:
    """List installed packages from manifest."""
    pkgs = list_all()
    if not pkgs:
        return "未安装任何指令包（manifest 为空）。"

    lines = [f"已安装 {len(pkgs)} 个指令包:", ""]
    for p in sorted(pkgs, key=lambda x: x.get("id", "")):
        directives = p.get("directives", [])
        lines.append(f"  {p['id']:20s} {p.get('type','?')}   {len(directives)} directives")
        for d in directives[:3]:
            lines.append(f"    - {d}")
        if len(directives) > 3:
            lines.append(f"    ... and {len(directives)-3} more")
        lines.append("")

    return "\n".join(lines)
