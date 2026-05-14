"""
text-cli;pro — Platform self-management: publish path as directive。

Promote registered path declarations into callable skill-domain directives。
pro only publishes — dependency validation and param formats read from path declaration。

Directives:
    AI:text-cli;pro,<path_id>,domain=<domain>,action=<action>  → 发布路径为指令
    AI:text-cli;pro,<path_id>,domain=<domain>,action=<action>,<中文域>,<中文动作>

示例:
    AI:text-cli;pro,photo_analysis,domain=skill,action=照片分析
    → 注册 @directive("skill", "照片分析")
    → text-cli;query visible skill;照片分析

Author: Tide 🌊
"""

from __future__ import annotations

import json
import logging
import pathlib

from core.registry import directive, dispatch

logger = logging.getLogger(__name__)
SCHEMA_DIR = pathlib.Path(__file__).parent / "schema"


def _find_path_schema(path_id: str) -> pathlib.Path | None:
    """Find a path_<id>.json in the schema directory."""
    candidate = SCHEMA_DIR / f"path_{path_id}.json"
    if candidate.is_file():
        return candidate
    # Also try with _schema suffix
    candidate2 = SCHEMA_DIR / f"{path_id}_schema.json"
    if candidate2.is_file():
        return candidate2
    return None


def _parse_pro_params(params: list[str]) -> tuple[str, str, str, str]:
    """Parse pro params: <path_id>,domain=X,action=Y[,<domain_cn>,<action_cn>]

    Returns (path_id, domain, action, domain_cn, action_cn).
    domain_cn/action_cn default to domain/action if not provided.
    """
    path_id = params[0].strip() if params else ""

    domain = ""
    action = ""
    domain_cn = ""
    action_cn = ""

    for p in params[1:]:
        ps = p.strip()
        if ps.startswith("domain="):
            domain = ps[7:]
        elif ps.startswith("action="):
            action = ps[7:]
        elif ps.startswith("domain_cn="):
            domain_cn = ps[10:]
        elif ps.startswith("action_cn="):
            action_cn = ps[10:]
        else:
            # Positional fallback: first unmatched → domain_cn, second → action_cn
            if not domain_cn:
                domain_cn = ps
            elif not action_cn:
                action_cn = ps

    if not domain_cn:
        domain_cn = domain
    if not action_cn:
        action_cn = action

    return path_id, domain, action, domain_cn, action_cn


def _register_skill_directive(
    domain: str, action: str, domain_cn: str, action_cn: str, path_id: str, path_def: dict
) -> tuple[bool, str]:
    """Register a skill directive that executes the path when called.

    This is the core of pro — turning a path declaration into a callable
    @directive that the registry can dispatch.
    """
    # Build the execution function as a closure over the path definition
    def _skill_handler(params: list[str]) -> str:
        """Execute the registered path as a skill directive."""
        from .text_cli_path import _execute_path
        initial_input = params[0] if params else ""
        return _execute_path(path_def, initial_input)

    _skill_handler.__name__ = f"_skill_{path_id}"

    # Register
    try:
        directive(domain, action)(_skill_handler)
    except Exception as e:
        return False, f"Directive registration failed: {e}"

    # Register Chinese variant if different
    if domain_cn and domain_cn != domain:
        try:
            directive(domain_cn, action_cn)(_skill_handler)
        except Exception as e:
            logger.warning("中文Directive registration failed: %s;%s — %s", domain_cn, action_cn, e)

    logger.info("Skill published: %s;%s → %s", domain, action, path_id)
    return True, "ok"


@directive("text-cli", "pro")
@directive("文本指令", "发布")
def text_cli_pro(params: list[str]) -> str:
    """Publish a registered path as a callable skill directive.

    Usage:
        AI:text-cli;pro,<path_id>,domain=<domain>,action=<action>[,<domain_cn>,<action_cn>]

    Example:
        AI:text-cli;pro,photo_analysis,domain=skill,action=照片分析
    """
    if len(params) < 3:
        return (
            "用法: AI:text-cli;pro,<path_id>,domain=<域>,action=<动作>[,<中文域>,<中文动作>]\n\n"
            "Publish a registered path as a callable directive. Path must be registered via --register first。\n"
            "示例: AI:text-cli;pro,photo_analysis,domain=skill,action=照片分析"
        )

    path_id, domain, action, domain_cn, action_cn = _parse_pro_params(params)

    if not path_id:
        return "Error: missing path_id"
    if not domain:
        return "Error: missing domain=（如 domain=skill）"
    if not action:
        return "Error: missing action=（如 action=照片分析）"

    # 1. Find path schema
    schema_path = _find_path_schema(path_id)
    if not schema_path:
        available = [f.stem for f in SCHEMA_DIR.glob("path_*.json")]
        hint = f"\nRegistered paths: {', '.join(available)}" if available else "\nNo registered paths. Use text-cli;path --register first。"
        return f"Registered path not found: {path_id}{hint}"

    # 2. Load and validate
    try:
        path_def = json.loads(schema_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        return f"Path file read error: {e}"

    # Check required declaration fields
    for field in ("version", "type", "steps"):
        if field not in path_def:
            return f"Path declaration incomplete: missing {field} field. Please re-run --register。"

    requires = path_def.get("requires", [])
    ptype = path_def.get("type", "skill")
    ver = path_def.get("version", "?")
    name = path_def.get("name", path_id)

    # 3. Check requires
    from core.registry import get_registered_directives
    available = set()
    for dom, actions in get_registered_directives().items():
        for act in actions:
            available.add(f"{dom};{act}")

    missing = [r for r in requires if r not in available]
    if missing:
        return (
            f"Cannot publish: the following required directives are unavailable\n"
            f"  缺失: {', '.join(missing)}\n"
            f"  Install missing capability packages first (text-cli;install)"
        )

    # 4. Register the skill directive
    ok, msg = _register_skill_directive(
        domain, action, domain_cn, action_cn, path_id, path_def
    )
    if not ok:
        return f"Publish failed: {msg}"

    # 5. Update the path schema to mark as published
    path_def["directives"] = path_def.get("directives", [])
    path_def["directives"].append({
        "domain": domain,
        "action": action,
        "domain_cn": domain_cn,
        "action_cn": action_cn,
        "usage": f"{domain};{action}",
        "usage_cn": f"{domain_cn};{action_cn}" if domain_cn else f"{domain};{action}",
        "description": f"Composite {ptype} — {'; '.join(requires)}",
        "description_cn": f"{ptype}复合技能 — Requires: {', '.join(requires)}",
    })

    try:
        schema_path.write_text(
            json.dumps(path_def, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as e:
        logger.warning("Failed to update path schema directives: %s", e)

    skill_call = f"{domain};{action}"
    return (
        f"✅ Published successfully: {name} (v{ver})\n"
        f"  Directive: {skill_call}\n"
        f"  Type: {ptype}\n"
        f"  Requires: {', '.join(requires)}\n"
        f"  → AI:{skill_call},<输入> is now callable\n"
        f"  → text-cli;query visible"
    )
