"""
text-cli;export + text-cli;packages + text-cli;repair-manifest — package lifecycle: export, list & repair.

Directives:
    text-cli;export,<id>[,--verify] → export single package to text-cli-package/
    text-cli;export-all             → export all installed packages
    text-cli;packages               → list installed packages with manifest info
    text-cli;repair-manifest        → scan schema dir, fill missing files.schema in manifest

Author: Tide 🌊 — 2026-05-17 / 2026-05-19
"""

import json
import logging
import os
import shutil
from pathlib import Path

from core.registry import directive
from .package_manifest import get, list_all, register as manifest_register, MANIFEST_PATH

logger = logging.getLogger(__name__)

PACKAGE_DIR = Path(os.environ.get("TEXT_CLI_PACKAGE_DIR", str(Path(os.environ.get("TEXT_CLI_HOME", str(Path.home() / "text-cli"))) / ".." / "text-cli-package")))
HANDLERS_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = HANDLERS_DIR.parent


@directive("text-cli", "export", domain_alias="文本指令", action_aliases={"export": "导出"})
@directive("text-cli", "export", domain_alias="文本指令", action_aliases={"export": "导出"})
    """Export a package to text-cli-package/<id>/"""
    if not params:
        return json.dumps({
            "status": "error",
            "reason": "Usage: text-cli;export,<package_id>[,--verify]"
        })

    pkg_id = params[0]
    do_verify = "--verify" in params
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
        source_path = pkg.get("source", "")

        # Copy handler
        handler_rel = files.get("handler", "")
        if handler_rel:
            src = SERVICE_ROOT / handler_rel
            dst_handler = dest / "handler.py"
            if src.exists() and src.resolve() != dst_handler.resolve():
                shutil.copy2(src, dst_handler)
            else:
                logger.warning("handler not found: %s", src)

        # Copy schema — try source dir first, fall back to handlers/schema
        schema_copied = False

        # 1. Source dir (text-cliV1/<name>/schema.json)
        source_dir = Path(source_path) if source_path else None
        if source_dir and source_dir.is_dir():
            s = source_dir / "schema.json"
            dst_schema = dest / "schema.json"
            if s.exists() and s.resolve() != dst_schema.resolve():
                shutil.copy2(s, dst_schema)
                schema_copied = True

        # 2. handlers/schema/<name>_schema.json
        if not schema_copied:
            schema_rel = files.get("schema", f"handlers/schema/{pkg_id}_schema.json")
            src = SERVICE_ROOT / schema_rel
            dst_schema = dest / "schema.json"
            if src.exists() and src.resolve() != dst_schema.resolve():
                shutil.copy2(src, dst_schema)
                schema_copied = True

        # 3. Generate minimal schema from manifest data
        if not schema_copied:
            directives_list = pkg.get("directives", [])
            if directives_list:
                schema_entries = []
                for d in directives_list:
                    parts = d.split(";", 1)
                    domain, action = parts if len(parts) == 2 else (pkg_id, d)
                    schema_entries.append({
                        "domain": domain,
                        "action": action,
                        "usage": d,
                        "params": [],
                    })
                gen = {
                    "id": pkg_id,
                    "name": pkg_id,
                    "runtime": "python",
                    "directives": schema_entries,
                }
                (dest / "schema.json").write_text(
                    json.dumps(gen, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                schema_copied = True
                logger.info("generated minimal schema for %s", pkg_id)

        if not schema_copied:
            logger.warning("no schema found for %s", pkg_id)

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
            **(_verify_export(dest, pkg_id, pkg_type, pkg) if do_verify else {}),
        }, ensure_ascii=False)

    except Exception as e:
        logger.exception("export failed for %s", pkg_id)
        return json.dumps({"status": "error", "reason": str(e)})


@directive("text-cli", "export-all", domain_alias="文本指令", action_aliases={"export-all": "全部导出"})
@directive("text-cli", "export-all", domain_alias="文本指令", action_aliases={"export-all": "全部导出"})
@directive("text-cli", "export-all", domain_alias="文本指令", action_aliases={"export-all": "全部导出"})
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


@directive("text-cli", "packages", domain_alias="文本指令", action_aliases={"packages": "已安装包"})
def text_cli_packages(params: list[str]) -> str:
@directive("text-cli", "packages", domain_alias="文本指令", action_aliases={"packages": "已安装包"})
@directive("text-cli", "packages", domain_alias="文本指令", action_aliases={"packages": "已安装包"})
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


# ── Verify helper ───────────────────────────────

def _verify_export(dest: Path, pkg_id: str, pkg_type: str, pkg: dict) -> dict:
    """Check exported package has all expected files."""
    missing = []
    present = []

    # handler (.py for python, .js for node)
    if pkg_type in ("python", "native"):
        hp = dest / "handler.py"
        (present if hp.exists() else missing).append("handler.py")
    elif pkg_type == "node":
        hp = dest / "handler.js"
        (present if hp.exists() else missing).append("handler.js")

    # schema.json
    sp = dest / "schema.json"
    (present if sp.exists() else missing).append("schema.json")

    # Check manifest's declared files
    files = pkg.get("files", {})
    if "requirements" in files:
        rp = dest / "requirements.txt"
        (present if rp.exists() else missing).append("requirements.txt")
    if "readme" in files:
        rp = dest / "README.md"
        (present if rp.exists() else missing).append("README.md")

    result = {
        "verified": len(missing) == 0,
        "present": present,
    }
    if missing:
        result["missing"] = missing
        result["status"] = "incomplete"
    return result


# ── Repair manifest ────────────────────────────

@directive("text-cli", "repair-manifest", domain_alias="文本指令", action_aliases={"repair-manifest": "修复清单"})
def text_cli_repair_manifest(params: list[str]) -> str:
    """Scan handlers/schema/ and fill missing files.schema in installed packages."""
@directive("text-cli", "repair-manifest", domain_alias="文本指令", action_aliases={"repair-manifest": "修复清单"})
@directive("text-cli", "repair-manifest", domain_alias="文本指令", action_aliases={"repair-manifest": "修复清单"})

    if not schema_dir.is_dir():
        return json.dumps({"status": "error", "reason": "schema dir not found"})

    repaired = []
    unchanged = []

    for pkg_id, pkg in packages.items():
        # Try exact match first, then underscore variant (hyphen→underscore mismatch)
        candidates = [
            f"{pkg_id}_schema.json",
            f"{pkg_id.replace('-', '_')}_schema.json",
        ]
        schema_path = None
        for c in candidates:
            sp = schema_dir / c
            if sp.exists():
                schema_path = sp
                schema_filename = c
                break

        if schema_path is None:
            continue

        files = pkg.get("files", {})
        current_schema = files.get("schema", "")

        # Check if schema path is missing or incorrect
        expected_schema = f"handlers/schema/{schema_filename}"
        if current_schema == expected_schema:
            unchanged.append(pkg_id)
            continue

        # Fix it
        files["schema"] = expected_schema
        pkg["files"] = files
        repaired.append(pkg_id)
        logger.info("repair-manifest: %s schema → %s", pkg_id, expected_schema)

    if repaired:
        _save_manifest_raw(packages)

    return json.dumps({
        "status": "ok",
        "repaired": repaired,
        "repaired_count": len(repaired),
        "unchanged": len(unchanged),
        "total_scanned": len(packages),
    }, ensure_ascii=False)


def _load_manifest_raw() -> dict:
    """Load raw manifest dict for repair operations."""
    try:
        with open(MANIFEST_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get("packages", {})
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_manifest_raw(packages: dict):
    """Persist raw manifest dict."""
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_PATH, 'w', encoding='utf-8') as f:
        json.dump({"packages": packages}, f, ensure_ascii=False, indent=2)
