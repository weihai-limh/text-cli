"""
text-cli;pro — A9 facade handler (skeleton).

User-friendly entry point that resolves a short name to its execution target.
Target types:
    path      → dispatches to text-cli;path with the resolved path file
    aggregate → dispatches to aggregate domain;action (via dispatch())

Configuration:
    service/config/pro_registry.json maps names to targets.

Examples:
    text-cli;pro,flower-care                → path target
    text-cli;pro,map-geocode,{"address":"北京"} → aggregate target

Author: Tide
"""

import json
import logging
from pathlib import Path

from core.registry import directive
from core.registry import dispatch as _dispatch
from core.registry import _ANCESTOR_CHAIN, _DEFERRED_KEYS

logger = logging.getLogger(__name__)

_PROJECT_ROOT: Path | None = None
_REGISTRY: dict = {}


def init_text_cli_pro_handler(project_root: str = None):
    global _PROJECT_ROOT, _REGISTRY
    if project_root:
        _PROJECT_ROOT = Path(project_root)
    _REGISTRY = _load_registry()
    logger.info("text-cli;pro initialised: %d entries", len(_REGISTRY))


def _load_registry() -> dict:
    if not _PROJECT_ROOT:
        return {}
    path = _PROJECT_ROOT / "config" / "pro_registry.json"
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


@directive("text-cli", "pro", domain_alias="文本指令", action_aliases={"pro": "发布"})
def text_cli_pro(params: list[str]) -> dict:
    if not params:
        return {
            "status": "error",
            "reason": "Usage: text-cli;pro,<name>[,<input_json>]"
        }

    name = params[0]
    entry = _REGISTRY.get(name)
    if not entry:
        return {
            "status": "error",
            "reason": f"pro '{name}' not registered",
            "available": list(_REGISTRY.keys()),
        }

    target_type = entry.get("type", "path")

    if target_type == "path":
        path_ref = entry.get("path", "")
        if not path_ref:
            return {"status": "error", "reason": "path target has no 'path' field"}

        # Check for re-entry cycle (只查不推 — _dispatch handles push/pop)
        resolved_key = f"path:{path_ref}"
        chain = _ANCESTOR_CHAIN.get()
        if resolved_key in chain:
            return {"status": "error",
                    "reason": f"call cycle detected: {resolved_key} re-entered (chain: {' → '.join(chain)})"}

        path_params = [path_ref]
        if len(params) > 1:
            path_params.extend(params[1:])

        try:
            return _dispatch("text-cli", "path", path_params)
        except Exception as e:
            logger.exception("pro → path dispatch failed: %s", name)
            return {"status": "error", "reason": str(e)}

    if target_type == "aggregate":
        domain = entry.get("domain", "")
        action = entry.get("action", "")
        if not domain or not action:
            return {"status": "error", "reason": "aggregate target missing domain/action"}

        # Check for re-entry cycle (只查不推)
        resolved_key = f"agg:{entry.get('name', name)}"
        chain = _ANCESTOR_CHAIN.get()
        if resolved_key in chain:
            return {"status": "error",
                    "reason": f"call cycle detected: {resolved_key} re-entered (chain: {' → '.join(chain)})"}

        agg_params = params[1:] if len(params) > 1 else []

        try:
            return _dispatch(domain, action, agg_params)
        except Exception as e:
            logger.exception("pro → aggregate dispatch failed: %s", name)
            return {"status": "error", "reason": str(e)}

    return {"status": "error", "reason": f"unknown target type: {target_type}"}
