"""
MCP 路由分发 — text-cli-service 的多后端路由决策

路由表从 text_cli_schema.json 动态派生（与 copilot 的 _build_mcp_registry 同构）。
无硬编码——加新 MCP tool 只需改 schema，重启即生效。
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

# ── schema 派生的运行时结构 ──
# 与 copilot _alias_map + _mcp_registry 完全同构

_alias_to_canonical: dict[str, str] = {}   # "腾讯地图;地址解析" → "tencentmap;geocode"
_routing_by_canonical: dict[str, dict] = {} # "tencentmap;geocode" → {server, tool, ...}


def _strip_prefix(directive: str) -> str:
    """去掉 AI:/指令: 前缀，返回纯 domain;action"""
    for prefix in ("AI:", "指令:"):
        if directive.startswith(prefix):
            return directive[len(prefix):].strip()
    return directive.strip()


def init_from_schema(schema: dict):
    """
    从 schema 构建 alias 映射和路由表。

    每次 _load_schema() 后调用，确保 schema 是路由的唯一数据源。

    与 copilot CopilotCore._build_mcp_registry 同构：
    - alias → canonical 从 directive/directive_zh 派生
    - routing 从 routing.backends 派生
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

        # routing: 取第一个 mcp backend
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
    """加载路由偏好配置。文件不存在则返回全 local。"""
    try:
        with open(PREF_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"default": "local", "preferences": {}}


def get_mcp_route(domain: str, action: str) -> dict | None:
    """
    获取指令的 MCP 路由配置。

    流程：alias → canonical → routing lookup
    """
    lookup = f"{domain};{action}"
    canonical = _alias_to_canonical.get(lookup, lookup)
    return _routing_by_canonical.get(canonical)


def decide_backend(domain: str, action: str) -> str:
    """
    决定使用哪个后端执行指令。

    Returns: "local" | "mcp"
    """
    prefs = load_preferences()
    lookup = f"{domain};{action}"
    canonical = _alias_to_canonical.get(lookup, lookup)

    # 1. 显式偏好优先（查原始 key 和 canonical key）
    for key in (lookup, canonical):
        if key in prefs.get("preferences", {}):
            return prefs["preferences"][key]

    # 2. 默认
    return prefs.get("default", "local")


def adapt_params(params: list, routing: dict) -> dict:
    """
    将 text-cli 位置参数适配为 MCP tool arguments。

    与 copilot _adapt_params_mcp 同构：
    - passthrough: 位置参数按 param_names 顺序映射
    - json_parse: 第一个参数解析为 JSON
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
            # JSON 中的逗号可能被解析器拆开，尝试拼接还原
            try:
                return _json.loads(",".join(params))
            except (json.JSONDecodeError, ValueError):
                return {"_raw": params[0]}

    # 未知 adapter → 原样传参，不吞错误
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
            sd_path = _SCHEMA_DIR.parent.parent / "packages" / sf.stem.replace("_schema", "") / "service-descriptor.json"
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
