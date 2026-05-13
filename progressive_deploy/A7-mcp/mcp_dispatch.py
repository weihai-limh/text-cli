"""
MCP routing dispatch — multi-backend routing decisions for text-cli-service

Routing table dynamically derived from text_cli_schema.json (isomorphic with copilot's _build_mcp_registry).
No hardcoding — adding a new MCP tool only requires schema changes, effective on restart.
"""

import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

PREF_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "routing_preferences.json")

# ── Schema-derived runtime structures ──
# Fully isomorphic with copilot's _alias_map + _mcp_registry

_alias_to_canonical: dict[str, str] = {}   # "tencentmap;geocode" → "tencentmap;geocode"
_routing_by_canonical: dict[str, dict] = {} # "tencentmap;geocode" → {server, tool, ...}


def _strip_prefix(directive: str) -> str:
    """Strip AI:/指令: prefix, return bare domain;action."""
    for prefix in ("AI:", "指令:"):
        if directive.startswith(prefix):
            return directive[len(prefix):].strip()
    return directive.strip()


def init_from_schema(schema: dict):
    """
    Build alias map and routing table from schema.

    Called after each _load_schema() to ensure schema is the single source of truth.

    Isomorphic with copilot CopilotCore._build_mcp_registry:
    - alias → canonical derived from directive/directive_zh
    - routing derived from routing.backends
    """
    global _alias_to_canonical, _routing_by_canonical
    _alias_to_canonical.clear()
    _routing_by_canonical.clear()

    for entry_id, entry in schema.items():
        routing = entry.get("routing")
        if not routing:
            continue

        # canonical key: directive → domain;action
        directive = entry.get("directive", "")
        canonical = _strip_prefix(directive)
        if not canonical:
            continue

        # identity mapping
        _alias_to_canonical[canonical] = canonical

        # Chinese alias
        zh_directive = entry.get("directive_zh", "")
        zh_key = _strip_prefix(zh_directive)
        if zh_key:
            _alias_to_canonical[zh_key] = canonical

        # routing: take the first mcp backend
        backends = routing.get("backends", [])
        for backend in backends:
            if backend.get("type") == "mcp":
                _routing_by_canonical[canonical] = {
                    "server": backend["server"],
                    "tool": backend["tool"],
                    "adapter": backend.get("adapter", "passthrough"),
                    "param_names": backend.get("param_names", []),
                    "timeout_ms": backend.get("timeout_ms", 30000),
                }
                break

    logger.info(
        "MCP routing from schema: %d canonicals, %d aliases, %d routes",
        len(_routing_by_canonical),
        len(_alias_to_canonical),
        len(_routing_by_canonical),
    )


def load_preferences() -> dict:
    """Load routing preference config. Returns all-local if file not found."""
    try:
        with open(PREF_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"default": "local", "preferences": {}}


def get_mcp_route(domain: str, action: str) -> Optional[dict]:
    """
    Get MCP routing config for a directive.

    Flow: alias → canonical → routing lookup
    """
    lookup = f"{domain};{action}"
    canonical = _alias_to_canonical.get(lookup, lookup)
    return _routing_by_canonical.get(canonical)


def decide_backend(domain: str, action: str) -> str:
    """
    Decide which backend to use for executing a directive.

    Returns: "local" | "mcp"
    """
    prefs = load_preferences()
    lookup = f"{domain};{action}"
    canonical = _alias_to_canonical.get(lookup, lookup)

    # 1. Explicit preference first (check raw key and canonical key)
    for key in (lookup, canonical):
        if key in prefs.get("preferences", {}):
            return prefs["preferences"][key]

    # 2. Default
    return prefs.get("default", "local")


def adapt_params(params: list, routing: dict) -> dict:
    """
    Adapt text-cli positional parameters to MCP tool arguments.

    Isomorphic with copilot _adapt_params_mcp:
    - passthrough: positional params mapped by param_names order
    - json_parse: first param parsed as JSON
    """
    adapter = routing.get("adapter", "passthrough")

    if adapter == "passthrough":
        param_names = routing.get("param_names", [])
        args = {}
        for i, name in enumerate(param_names):
            if i < len(params):
                args[name] = params[i]
        return args

    if adapter == "json_parse" and params:
        try:
            import json as _json
            return _json.loads(params[0])
        except (json.JSONDecodeError, ValueError):
            # JSON commas may have been split by the parser, attempt to rejoin
            try:
                return _json.loads(",".join(params))
            except (json.JSONDecodeError, ValueError):
                return {"_raw": params[0]}

    # Unknown adapter → pass through raw, don't swallow errors
    return {"_params": params}
