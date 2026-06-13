"""
skill_endpoint — 骨架内置白名单暴露层

读取 config/skills_exposure.json，控制哪些已发布的 composite path
出现在 /text-cli/skills 端点上。默认不暴露任何能力。

安全模型：
  白名单优先。未在 skills_exposure.json 中列出的 path 不会对外暴露。
  配置不存在时返回空列表，不报错。

Visibility 三级：
  - internal   : 不对外暴露
  - restricted : 需 scope 授权
  - public     : 开放

Author: Tide 🌊
"""

from __future__ import annotations

import json
import logging
import pathlib

logger = logging.getLogger("text-cli.skill_endpoint")

# ── 路径 ──

_CONFIG_DIR = pathlib.Path(__file__).resolve().parent.parent / "config"
_SCHEMA_DIR = pathlib.Path(__file__).resolve().parent / "schema"

_EXPOSURE_FILE = _CONFIG_DIR / "skills_exposure.json"
_EXPOSURE_EXAMPLE = _CONFIG_DIR / "skills_exposure.example.json"


# ── 加载配置 ──

def _load_exposure() -> dict:
    """Load skills_exposure.json. Returns empty dict if not found."""
    path = _EXPOSURE_FILE
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read skills_exposure.json — %s", exc)
        return {}


def _load_path_schemas() -> list[dict]:
    """Load all path_*.json declarations from schema/ directory."""
    schemas = []
    if not _SCHEMA_DIR.exists():
        return schemas
    for f in sorted(_SCHEMA_DIR.glob("path_*.json")):
        try:
            schemas.append(json.loads(f.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read path schema: %s — %s", f.name, exc)
    return schemas


# ── 白名单过滤 ──

def _get_visibility(exposure: dict, skill_id: str) -> str | None:
    """Get visibility for a skill, or None if not exposed."""
    entry = exposure.get(skill_id)
    if not isinstance(entry, dict):
        return None
    vis = entry.get("visibility", "internal")
    if vis == "internal":
        return None
    return vis


# ── 对外接口 ──

def list_skills() -> dict:
    """List all externally visible skills (GET /text-cli/skills)."""
    exposure = _load_exposure()
    if not exposure:
        return {}

    schemas = _load_path_schemas()
    schema_map = {s.get("id", ""): s for s in schemas if s.get("id")}

    result = {}
    for skill_id, entry in exposure.items():
        if not isinstance(entry, dict):
            continue
        vis = entry.get("visibility", "internal")
        if vis == "internal":
            continue

        schema = schema_map.get(skill_id, {})
        result[skill_id] = {
            "visibility": vis,
            "description": entry.get("description_public", schema.get("description", "")),
            "description_cn": entry.get("description_public", schema.get("description_cn", schema.get("description", ""))),
            "version": schema.get("version", "?"),
            "rate_limit": entry.get("rate_limit"),
            "credit_cost": entry.get("credit_cost", 0),
        }
        # Include endpoints only for public/restricted
        if vis in ("public", "restricted"):
            result[skill_id]["endpoint_detail"] = f"/text-cli/skills/{skill_id}"
            result[skill_id]["endpoint_execute"] = f"POST /text-cli/skills/{skill_id}"

    return result


def get_skill_detail(skill_id: str) -> dict | None:
    """Get full detail for a single exposed skill (GET /text-cli/skills/{id})."""
    exposure = _load_exposure()
    if not exposure:
        return None

    entry = exposure.get(skill_id)
    if not isinstance(entry, dict):
        return None

    vis = entry.get("visibility", "internal")
    if vis == "internal":
        return None

    # Load the path schema to fill in details
    schemas = _load_path_schemas()
    schema = next((s for s in schemas if s.get("id") == skill_id), {})

    return {
        "id": skill_id,
        "visibility": vis,
        "description": entry.get("description_public", schema.get("description", "")),
        "description_cn": entry.get("description_public", schema.get("description_cn", schema.get("description", ""))),
        "version": schema.get("version", "?"),
        "input_schema": schema.get("input_schema", {}),
        "output_schema": schema.get("output_schema", {}),
        "steps": schema.get("steps", []),
        "requires": schema.get("requires", []),
        "rate_limit": entry.get("rate_limit"),
        "credit_cost": entry.get("credit_cost", 0),
        "source_file": schema.get("source_file", ""),
    }



