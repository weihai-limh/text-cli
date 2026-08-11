"""
MCP routing dispatch — text-cli-service multi-backend routing decision.

Routing table is dynamically derived from text_cli_schema.json
(isomorphic with copilot's _build_mcp_registry).
No hard-coding — adding a new MCP tool only requires a schema change,
restart to take effect.
"""

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

PREF_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "routing_preferences.json")
_SERVICE_ROOT = Path(__file__).resolve().parent.parent
_SCHEMA_PATH = _SERVICE_ROOT / "config" / "text_cli_schema.json"
_SCHEMA_DIR = _SERVICE_ROOT / "handlers" / "schema"

# ── schema-derived runtime structures ──
# Isomorphic with copilot _alias_map + _mcp_registry

_alias_to_canonical: dict[str, str] = {}   # "tencentmap;geocode" → "tencentmap;geocode"
_routing_by_canonical: dict[str, dict] = {} # "tencentmap;geocode" → {server, tool, ...}


def _strip_prefix(directive: str) -> str:
    """Strip AI:/指令: prefix, return bare domain;action"""
    for prefix in ("AI:", "指令:"):
        if directive.startswith(prefix):
            return directive[len(prefix):].strip()
    return directive.strip()


def init_from_schema(schema: dict):
    """
    Build alias map and routing table from schema.

    Called after every _load_schema() to ensure schema is the sole data source
    for routing. Isomorphic with copilot CopilotCore._build_mcp_registry:
    - alias → canonical derived from directive/directive_zh
    - routing derived from routing.backends
    """
    _alias_to_canonical.clear()
    _routing_by_canonical.clear()

    for entry in schema.values():
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

        # routing: take first mcp backend
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
    """Load routing preferences config. Returns all-local if file missing."""
    try:
        with open(PREF_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"default": "local", "preferences": {}}


def get_mcp_route(domain: str, action: str) -> dict | None:
    """
    Get MCP routing config for a directive.

    Flow: alias → canonical → routing lookup
    """
    lookup = f"{domain};{action}"
    canonical = _alias_to_canonical.get(lookup, lookup)
    return _routing_by_canonical.get(canonical)


def decide_backend(domain: str, action: str) -> str:
    """
    Decide which backend to use for execution.

    Returns: "local" | "mcp"
    """
    prefs = load_preferences()
    lookup = f"{domain};{action}"
    canonical = _alias_to_canonical.get(lookup, lookup)

    # 1. explicit preference first (check both raw and canonical keys)
    for key in (lookup, canonical):
        if key in prefs.get("preferences", {}):
            return prefs["preferences"][key]

    # 2. default
    return prefs.get("default", "local")


def adapt_params(params: list, routing: dict) -> dict:
    """
    Adapt text-cli positional params to MCP tool arguments.

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
            # commas may have been split by parser, try reassembly
            try:
                return _json.loads(",".join(params))
            except (json.JSONDecodeError, ValueError):
                return {"_raw": params[0]}

    # unknown adapter -> pass-through raw params
    return {"_params": params}


def refresh_routes():
    """
    Re-build MCP routing table from text_cli_schema.json + installed package schemas.

    Called after install/uninstall to keep the routing table in sync with
    runtime-installed MCP packages without requiring a restart.
    """
    merged: dict = {}

    # 1. Load static schema
    if _SCHEMA_PATH.exists():
        try:
            merged.update(json.loads(_SCHEMA_PATH.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to read %s: %s", _SCHEMA_PATH.name, e)

    # 2. Merge runtime-installed MCP package schemas
    if _SCHEMA_DIR.exists():
        for sf in sorted(_SCHEMA_DIR.glob("*_schema.json")):
            try:
                pkg = json.loads(sf.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if pkg.get("runtime") != "mcp":
                continue

            # Load service-descriptor for mcporter routing info
            sd_path = _SCHEMA_DIR.parent.parent / "packages" / sf.stem.replace("_schema", "").replace("_", "-") / "service-descriptor.json"
            sd = {}
            if sd_path.exists():
                try:
                    sd = json.loads(sd_path.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    pass
            mcp_server = sd.get("mcp_server", "")
            tools = {t["name"]: t for t in sd.get("tools", [])} if sd.get("tools") else {}

            # Build routing entries for each directive
            directives = pkg.get("directives", [])
            if isinstance(directives, dict):
                directives = list(directives.values())
            for d in directives:
                domain = d.get("domain", "")
                action = d.get("action", "")
                if not domain or not action:
                    continue
                canonical = f"{domain};{action}"
                tool_def = tools.get(action, {})
                merged[canonical] = {
                    "directive": f"AI:{canonical}",
                    "directive_zh": d.get("directive_zh", ""),
                    "routing": {
                        "backends": [{
                            "type": "mcp",
                            "server": mcp_server,
                            "tool": tool_def.get("tool", action),
                            "adapter": d.get("adapter", "passthrough"),
                            "param_names": d.get("param_names", []),
                            "timeout_ms": d.get("timeout_ms", 30000),
                        }]
                    }
                }

    # 3. Rebuild routing tables
    init_from_schema(merged)
    logger.info("MCP routing refreshed: %d routes", len(_routing_by_canonical))
