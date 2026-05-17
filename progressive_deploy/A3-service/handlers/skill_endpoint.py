"""
Skills discovery & execution endpoint.

Exposes published paths (via text-cli;pro) filtered through
skills_exposure.json. Only "public" and "restricted" skills
appear; "internal" skills (pro-published but not in exposure
config) are hidden from /skills.

Endpoints:
    GET  /text-cli/skills          → list exposed skills
    GET  /text-cli/skills/<id>     → skill detail + steps
    POST /text-cli/skills/<id>     → execute skill (auth required)

Visibility model:
    internal   → text-cli;query only, hidden from /skills
    restricted → /skills visible, call requires scope=skill:<id>
    public     → /skills visible, any valid access_token

Author: Tide 🌊 · 2026-05-14
"""

from __future__ import annotations

import json
import logging
import pathlib
import time
from typing import Optional

logger = logging.getLogger("text-cli.skills")

SCHEMA_DIR = pathlib.Path(__file__).parent / "schema"
EXPOSURE_PATH = pathlib.Path(__file__).parent.parent / "config" / "skills_exposure.json"
MANIFEST_PATH = pathlib.Path(__file__).parent.parent / "config" / "service_manifest.json"

# Simple in-memory idempotency cache
_idempotency_cache: dict[str, dict] = {}
_IDEMPOTENCY_TTL = 300  # seconds


def _load_manifest() -> dict:
    """Load service manifest whitelist."""
    try:
        with open(MANIFEST_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _get_whitelist() -> list[str]:
    """Get whitelist directives. Empty = expose all (backward compatible)."""
    manifest = _load_manifest()
    return manifest.get("public_directives", [])
def _load_exposure() -> dict:
    """Load skills exposure configuration."""
    try:
        with open(EXPOSURE_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _load_path_schemas() -> list[dict]:
    """Load all path_*.json from schema dir."""
    if not SCHEMA_DIR.exists():
        return []
    schemas = []
    for f in sorted(SCHEMA_DIR.glob("path_*.json")):
        try:
            schemas.append(json.loads(f.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    return schemas


def _filter_exposed(paths: list[dict], exposure: dict) -> list[dict]:
    """Return only paths whose visibility is public or restricted.

    A path is "exposed" if:
    - Its id appears in exposure config
    - visibility is "public" or "restricted" (not internal/absent)
    """
    result = []
    for p in paths:
        pid = p.get("id", "")
        exp = exposure.get(pid, {})
        visibility = exp.get("visibility", "internal")

        if visibility not in ("public", "restricted"):
            continue

        # Build public-facing card
        card = {
            "id": pid,
            "name": p.get("name_cn", p.get("name", pid)),
            "name_en": p.get("name", pid),
            "version": p.get("version", "?"),
            "type": p.get("type", "skill"),
            "description": exp.get("description_public", p.get("description_cn", "")),
            "description_en": exp.get("description_public_en", p.get("description", "")),
            "visibility": visibility,
            "requires": p.get("requires", []),
            "input_schema": p.get("input_schema", {}),
            "output_schema": p.get("output_schema", {}),
            "rate_limit": exp.get("rate_limit"),
            "credit_cost": exp.get("credit_cost", 0),
        }
        result.append(card)

    return result


def _find_skill(skill_id: str) -> Optional[dict]:
    """Find a skill by id in registered paths. Returns full path schema or None."""
    schema_path = SCHEMA_DIR / f"path_{skill_id}.json"
    if not schema_path.is_file():
        return None
    try:
        return json.loads(schema_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _check_idempotency(key: str) -> Optional[dict]:
    """Check idempotency cache. Returns cached result or None."""
    entry = _idempotency_cache.get(key)
    if entry and time.time() - entry["ts"] < _IDEMPOTENCY_TTL:
        return entry["result"]
    # Clean expired
    if entry:
        del _idempotency_cache[key]
    return None


def _cache_idempotency(key: str, result: dict):
    """Store result in idempotency cache."""
    _idempotency_cache[key] = {
        "ts": time.time(),
        "result": result,
    }


def list_skills(exposure: dict = None) -> dict:
    """Build skills list for GET /text-cli/skills (paths + aggregates)."""
    if exposure is None:
        exposure = _load_exposure()
    whitelist = _get_whitelist()
    paths = _load_path_schemas()
    exposed = _filter_exposed(paths, exposure)

    # Add aggregate directives in whitelist
    from core.registry import get_registered_directives
    directives = get_registered_directives()
    seen_ids = {s["id"] for s in exposed}

    for directive_str in whitelist:
        parts = directive_str.split(";", 1)
        if len(parts) != 2:
            continue
        domain, action = parts
        agg_id = f"{domain}-{action}"
        if agg_id in seen_ids:
            continue
        seen_ids.add(agg_id)
        # Determine type — aggregate if domain has an aggregate config
        try:
            from main import _aggregates
            domain_type = "aggregate" if _aggregates.get(domain) else "native"
        except (ImportError, AttributeError):
            domain_type = "aggregate" if domain in ("map", "weather", "web") else "native"
        exposed.append({
            "id": agg_id,
            "name": directive_str,
            "name_en": directive_str,
            "version": "1.0.0",
            "type": domain_type,
            "description": f"{domain} {action}",
            "visibility": "public",
            "input_schema": {"type": "string"},
            "output_schema": {},
            "requires": [],
        })
    return {
        "skills": exposed,
        "count": len(exposed),
    }


def get_skill_detail(skill_id: str) -> Optional[dict]:
    """Build skill detail for GET /text-cli/skills/<id>."""
    exposure = _load_exposure()
    exp = exposure.get(skill_id, {})
    visibility = exp.get("visibility", "internal")

    if visibility not in ("public", "restricted"):
        return None

    schema = _find_skill(skill_id)
    if not schema:
        return None

    directives = schema.get("directives", [])
    if not directives:
        return None  # Not yet published via pro

    return {
        "id": skill_id,
        "name": schema.get("name_cn", schema.get("name", skill_id)),
        "name_en": schema.get("name", skill_id),
        "version": schema.get("version", "?"),
        "type": schema.get("type", "skill"),
        "mode": schema.get("mode", "toolchain"),
        "visibility": visibility,
        "description": exp.get("description_public", schema.get("description_cn", "")),
        "description_en": exp.get("description_public_en", schema.get("description", "")),
        "input_schema": schema.get("input_schema", {}),
        "output_schema": schema.get("output_schema", {}),
        "requires": schema.get("requires", []),
        "steps": schema.get("steps", []),
        "directives": directives,
        "rate_limit": exp.get("rate_limit"),
        "credit_cost": exp.get("credit_cost", 0),
    }


def execute_skill(skill_id: str, params: dict, token_scope: list[str] = None) -> dict:
    """Execute a skill via POST /text-cli/skills/<id>.

    params should contain:
        "input": str — the skill input
        "idempotency_key": str (optional)

    Returns: {"status": "ok"|"partial"|"error", "result": ..., "delegated": [...]}
    """
    exposure = _load_exposure()
    exp = exposure.get(skill_id, {})
    visibility = exp.get("visibility", "internal")

    if visibility not in ("public", "restricted"):
        return {"status": "error", "error": "skill_not_exposed",
                "message": f"技能 '{skill_id}' 未对外暴露"}

    # Auth check for restricted skills
    if visibility == "restricted":
        allowed = exp.get("allowed_scopes", [])
        if not token_scope or not any(s in allowed for s in token_scope):
            return {"status": "error", "error": "unauthorized",
                    "message": f"技能 '{skill_id}' 需要 scope: {', '.join(allowed)}"}

    # Idempotency check
    idem_key = params.get("idempotency_key", "")
    if idem_key:
        cached = _check_idempotency(idem_key)
        if cached:
            return cached

    # Load and validate
    schema = _find_skill(skill_id)
    if not schema:
        return {"status": "error", "error": "not_found",
                "message": f"技能 '{skill_id}' 未注册"}

    if not schema.get("directives"):
        return {"status": "error", "error": "not_published",
                "message": f"技能 '{skill_id}' 已注册但未发布 (text-cli;pro)"}

    # Execute
    from .text_cli_path import _execute_path
    initial_input = params.get("input", "")

    try:
        exec_result = _execute_path(schema, initial_input)
    except Exception as e:
        return {"status": "error", "error": "execution_failed",
                "message": str(e)}

    # Determine status from execution output
    if "[部分完成]" in exec_result:
        status = "partial"
    elif "执行异常" in exec_result or "[错误]" in exec_result:
        status = "error"
    else:
        status = "ok"

    result = {
        "status": status,
        "skill_id": skill_id,
        "result": exec_result,
    }

    # Cache if idempotent
    if idem_key:
        _cache_idempotency(idem_key, result)

    return result
