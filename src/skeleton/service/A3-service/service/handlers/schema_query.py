"""
text-cli;query — 元指令：动态发现当前运行时全量可调用指令（A3 + A2 proxy）。

读取 handlers/schema/*.json，合并为统一指令表。
支持多种输出格式和过滤器。尊重 no_schema.json 的隐藏规则。

text-cli 是平台自管理域（system runtime），不参与包安装/卸载生命周期。

Directives:
    AI:text-cli;query                          → 全量纯文本（含 A2 proxy）
    AI:text-cli;query,json                     → JSON 格式
    AI:text-cli;query,compact                  → 极简格式
    AI:text-cli;query,python|js|mcp            → 按 runtime 过滤
    AI:text-cli;query,category[,<name>]        → 按分类过滤 / 列出分类
    AI:text-cli;query,collection               → 用户自定义精选指令集
    AI:text-cli;query,path                     → 路径声明列表（composite runtime）
    AI:text-cli;query,delta                    → 变化报告
    AI:text-cli;query,<keyword>                → 关键词搜索
    AI:文本指令;查询                            → 中文别名

Author: Tide 🌊
"""

from __future__ import annotations

import json
import logging
import pathlib
import urllib.error
import urllib.request
from urllib.parse import urlparse

from core.registry import directive

logger = logging.getLogger("text-cli.schema_query")

# ── A2 proxy discovery ──

def _fetch_a2_directives() -> list[dict]:
    """Fetch A2 copilot directive list via GET /text_cli_schema.json."""
    a2_url = "http://127.0.0.1:20260/text_cli_schema.json"
    if urlparse(a2_url).scheme not in ('http', 'https'):
        return []
    try:
        req = urllib.request.Request(a2_url, method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("directives", [])
    except Exception as e:
        logger.debug("A2 copilot unreachable: %s", e)
        return []

SCHEMA_DIR = pathlib.Path(__file__).resolve().parent / "schema"

RESERVED = frozenset({"all", "json", "compact", "python", "js", "mcp",
                       "category", "delta", "collection", "path"})

# ── Supported locale codes for query tail parameter ──
# Matched against SPEC locales field. Append here to enable new languages.
_SUPPORTED_LOCALES = frozenset({"zh", "en"})


def _l(d: dict, field: str, lang: str) -> str:
    """Resolve localized field from dict d.

    auto → canonical field (name/description/usage) — SPEC minimum guarantee.
    zh   → field_zh ?? field   — fallback to canonical when locale absent.
    en   → field_en ?? field
    Fallback is safe because SPEC requires canonical fields to be present
    in every schema. Locale suffixes (_zh/_en) are optional overlays.
    """
    if lang == "auto":
        return d.get(field, "")
    key = f"{field}_{lang}"
    return d.get(key) or d.get(field, "")


def _resolve_language(params: list[str], config: dict | None = None) -> str:
    """Resolve output language for query rendering.

    Priority:
      1. Caller tail parameter (if last param is in _SUPPORTED_LOCALES) → pop and use
      2. Server config instructions_language (zh | en | auto)
      3. auto (canonical fields only)
    """
    if params and params[-1].strip() in _SUPPORTED_LOCALES:
        return params.pop().strip()
    if config:
        return config.get("server", {}).get("instructions_language", "auto")
    return "auto"

# ── 加载 ──

def _load_schemas() -> list[dict]:
    """Load all *_schema.json + path_*.json from handlers/schema/"""
    schemas = []
    if not SCHEMA_DIR.exists():
        return schemas
    # Package schema + path declarations (unified glob discovery)
    files = sorted(SCHEMA_DIR.glob("*_schema.json")) + sorted(SCHEMA_DIR.glob("path_*.json"))
    for f in files:
        try:
            schemas.append(json.loads(f.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read schema: %s — %s", f.name, exc)
    return schemas


def _load_no_schema() -> dict:
    """加载 no_schema.json 过滤规则"""
    path = SCHEMA_DIR / "no_schema.json"
    if not path.exists():
        return {"hidden": [], "hidden_domains": [], "hidden_categories": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"hidden": [], "hidden_domains": [], "hidden_categories": []}


# ── 过滤 ──

def _apply_no_schema(directives: list[dict], no_schema: dict) -> list[dict]:
    """三层过滤：hidden > hidden_domains > hidden_categories"""
    hidden = {(h["domain"], h["action"]) for h in no_schema.get("hidden", [])}
    hidden_domains = set(no_schema.get("hidden_domains", []))
    hidden_categories = set(no_schema.get("hidden_categories", []))

    result = []
    for d in directives:
        domain = d.get("domain", "")
        action = d.get("action", "")
        pkg = d.get("_package", {})
        category = pkg.get("category", "")

        if domain in hidden_domains:
            continue
        if category in hidden_categories:
            continue
        if (domain, action) in hidden:
            continue
        result.append(d)
    return result


def _flatten_directives(schemas: list[dict]) -> list[dict]:
    """Flatten schema list into flat directive list with package metadata。

    For composite paths, generate synthetic entries from declaration fields。
    """
    result = []
    for s in schemas:
        runtime = s.get("runtime", "python")
        pkg_meta = {
            "id": s.get("id", ""),
            "name": s.get("name", ""),
            "name_zh": s.get("name_zh", ""),
            "runtime": runtime,
            "category": s.get("category", s.get("type", "")),
            "description": s.get("description", ""),
            "description_zh": s.get("description_zh", ""),
        }

        # Composite path/skill entries — show as pending publication
        if runtime == "composite":
            ptype = s.get("type", "skill")
            ver = s.get("version", "?")
            reqs = s.get("requires", [])
            has_directives = bool(s.get("directives", []))

            if has_directives:
                # Already published via pro — show its directives
                for d in s.get("directives", []):
                    entry = dict(d)
                    entry["_package"] = pkg_meta
                    result.append(entry)
            else:
                # Not yet published — show as pending composite
                req_str = ", ".join(reqs) if reqs else "(none)"
                result.append({
                    "domain": "skill",
                    "action": s.get("name_zh", s.get("id", "")),
                    "domain_zh": "技能",
                    "action_zh": s.get("name_zh", s.get("id", "")),
                    "usage": f"skill;{s.get('name_zh', s.get('id', ''))}",
                    "usage_zh": f"skill;{s.get('name_zh', s.get('id', ''))}",
                    "description": f"[{ptype} v{ver}] {s.get('description', '')}",
                    "description_zh": f"[{ptype} v{ver}] {s.get('description_zh', s.get('description', ''))}\n    ─ 依赖: {req_str}\n    ─ 状态: 待发布 (text-cli;pro)",
                    "_package": pkg_meta,
                })
            continue

        for d in s.get("directives", []):
            entry = dict(d)
            entry["_package"] = pkg_meta
            result.append(entry)
    return result


def _collect(all_directives: list[dict]) -> list[dict]:
    """Full collection: load → flatten → filter"""
    no_schema = _load_no_schema()
    return _apply_no_schema(all_directives, no_schema)


# ── 过滤器 ──

def _filter_runtime(directives: list[dict], rt: str) -> list[dict]:
    return [d for d in directives
            if d.get("_package", {}).get("runtime", "python") == rt]


def _filter_category(directives: list[dict], cat: str) -> list[dict]:
    return [d for d in directives
            if d.get("_package", {}).get("category", "") == cat]


def _list_categories(directives: list[dict]) -> list[str]:
    cats = {d.get("_package", {}).get("category", "") for d in directives}
    return sorted(c for c in cats if c)


def _filter_composite(directives: list[dict]) -> list[dict]:
    """Filter to only composite runtime entries (path declarations)."""
    return [d for d in directives
            if d.get("_package", {}).get("runtime", "python") == "composite"]


_CONFIG_DIR = pathlib.Path(__file__).resolve().parent.parent / "config"


def _load_collection_directives() -> list[dict]:
    """Load user-defined collection from config/collection_text_cli.json.

    Returns a list of (domain, action) tuples defined in the collection.
    Returns empty list if config file does not exist or is invalid.
    """
    path = _CONFIG_DIR / "collection_text_cli.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        items = data.get("directives", [])
        return [(item["domain"], item["action"]) for item in items
                if isinstance(item, dict) and "domain" in item and "action" in item]
    except (json.JSONDecodeError, OSError, KeyError) as exc:
        logger.warning("Failed to load collection config: %s — %s", path.name, exc)
        return []


def _filter_by_collection(directives: list[dict], collection: list[tuple]) -> list[dict]:
    """Filter directives to only those matching (domain, action) pairs in collection."""
    if not collection:
        return []
    wanted = set(collection)
    return [d for d in directives
            if (d.get("domain", ""), d.get("action", "")) in wanted]


def _keyword_search(directives: list[dict], keyword: str) -> list[dict]:
    kw = keyword.lower()
    result = []
    for d in directives:
        pkg = d.get("_package", {})
        searchable = " ".join([
            d.get("domain", ""), d.get("domain_zh", ""),
            d.get("action", ""), d.get("action_zh", ""),
            d.get("description", ""), d.get("description_zh", ""),
            pkg.get("name", ""), pkg.get("name_zh", ""),
            pkg.get("description", ""), pkg.get("description_zh", ""),
        ]).lower()
        if kw in searchable:
            result.append(d)
    return result


# ── 渲染 ──

def _render_text(directives: list[dict], lang: str = "auto") -> str:
    if not directives:
        return "═══ Available directives ═══\n\n(none)"

    lines = ["═══ Available directives ═══\n"]

    # Group by package
    by_pkg: dict[str, list[dict]] = {}
    pkg_order = []
    for d in directives:
        pkg_name = _l(d["_package"], "name", lang)
        if pkg_name not in by_pkg:
            by_pkg[pkg_name] = []
            pkg_order.append(pkg_name)
        by_pkg[pkg_name].append(d)

    for pkg_name in pkg_order:
        entries = by_pkg[pkg_name]
        pkg = entries[0]["_package"]
        pkg_id = pkg.get("name", "")
        lines.append(f"{pkg_name} · {pkg_id}" if pkg_id and pkg_id != pkg_name else pkg_name)
        desc = _l(pkg, "description", lang)
        if desc:
            lines.append(f"  {desc}")
        for d in entries:
            usage = _l(d, "usage", lang)
            lines.append(f"  {usage}")
            ddesc = _l(d, "description", lang)
            if ddesc:
                lines.append(f"    ─ {ddesc}")
        lines.append("")

    # Append A2 proxy reachable directives
    a2_directives = _fetch_a2_directives()
    if a2_directives:
        lines.append("A2 copilot (127.0.0.1:20260)")
        for d in a2_directives:
            op_id = d.get("id") or f"{d.get('domain', '')};{d.get('action', '')}"
            usage = _l(d, "usage", lang) or op_id
            ddesc = _l(d, "description", lang)
            if ddesc:
                lines.append(f"  {usage}:{ddesc}")
            else:
                lines.append(f"  {usage}")
        lines.append("")

    return "\n".join(lines)


def _render_json(directives: list[dict]) -> str:
    """JSON 格式输出，剥离 _package 内部字段"""
    clean = []
    for d in directives:
        entry = {k: v for k, v in d.items() if k != "_package"}
        pkg = d.get("_package", {})
        entry["package"] = pkg.get("id", "")
        entry["runtime"] = pkg.get("runtime", "")
        clean.append(entry)
    return json.dumps({"directives": clean}, ensure_ascii=False, indent=2)


def _render_compact(directives: list[dict]) -> str:
    """极简格式：每行一个指令（含 A2 代理可达指令）"""
    lines = []
    for d in directives:
        usage = d.get("usage", f"{d['domain']};{d['action']}")
        lines.append(usage)
    # 追加 A2 代理可达的指令
    a2_directives = _fetch_a2_directives()
    if a2_directives:
        for d in a2_directives:
            op_id = d.get("id") or f"{d.get('domain', '')};{d.get('action', '')}"
            usage = d.get("usage", d.get("usage_zh", op_id))
            lines.append(usage if usage else op_id)
    return "\n".join(lines)


# ── delta 占位 ──

DELTA_STATE = SCHEMA_DIR / ".delta_state.json"


def _render_delta(directives: list[dict]) -> str:
    """变化报告（当前只返回指令总数）"""
    prev = {}
    if DELTA_STATE.exists():
        try:
            prev = json.loads(DELTA_STATE.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    current = {f"{d['domain']};{d['action']}" for d in directives}
    prev_set = set(prev.get("directives", []))

    added = current - prev_set
    removed = prev_set - current

    # 保存当前状态
    DELTA_STATE.write_text(json.dumps(
        {"directives": sorted(current)},
        ensure_ascii=False,
    ))

    if not added and not removed:
        return "═══ delta ═══\n(unchanged)"

    lines = ["═══ delta ═══"]
    for a in sorted(added):
        lines.append(f"+ {a}")
    for r in sorted(removed):
        lines.append(f"- {r}")
    return "\n".join(lines)


# ── handler ──

@directive("text-cli", "query", domain_alias="文本指令", action_aliases={"query": "查询"})
def schema_query(params: list[str]) -> dict:
    """
    元指令：动态发现运行时全部Available directives。

    参数模式:
        (空) / all              → 全量纯文本
        json                    → JSON 格式
        compact                 → 极简格式
        python / js / mcp       → 按 runtime 过滤
        category                → 列出所有分类
        category,<分类名>       → 按分类过滤
        delta                   → 变化报告
        <其他关键词>             → 关键词搜索

    尾参可选语言覆盖: ,zh | ,en (e.g. AI:text-cli;query,compact,zh)
    """
    # ── Resolve language (caller tail param override → server config default) ──
    try:
        from core.config import load_config
        _cfg = load_config()
    except Exception:
        _cfg = None
    lang = _resolve_language(params, _cfg)

    mode = params[0].strip() if params else "all"
    if not mode:
        mode = "all"

    all_schemas = _load_schemas()
    all_directives = _flatten_directives(all_schemas)
    directives = _collect(all_directives)

    if not directives:
        return {"status": "ok", "text": "(no registered directives)", "count": 0}


    # ── 模式分发 ──

    if mode == "all":
        return {"status": "ok", "text": _render_text(directives, lang), "count": len(directives)}

    if mode == "json":
        raw = _render_json(directives)
        result = json.loads(raw)
        return {"status": "ok", "directives": result.get("directives", []), "count": len(result.get("directives", []))}

    if mode == "compact":
        return {"status": "ok", "text": _render_compact(directives), "count": len(directives)}

    if mode in ("python", "js", "mcp"):
        filtered = _filter_runtime(directives, mode)
        return {"status": "ok", "text": _render_text(filtered, lang), "count": len(filtered)}

    if mode == "delta":
        return {"status": "ok", "text": _render_delta(directives), "count": len(directives)}

    if mode == "category":
        if len(params) > 1 and params[1].strip():
            filtered = _filter_category(directives, params[1].strip())
            return {"status": "ok", "text": _render_text(filtered, lang), "count": len(filtered)}
        cats = _list_categories(directives)
        if cats:
            return {"status": "ok", "categories": cats, "count": len(cats)}
        return {"status": "ok", "categories": [], "count": 0}

    if mode == "collection":
        collection_items = _load_collection_directives()
        if not collection_items:
            return {"status": "error", "reason": "config/collection_text_cli.json not found. Copy .example to configure."}
        filtered = _filter_by_collection(directives, collection_items)
        if filtered:
            return {"status": "ok", "text": _render_text(filtered, lang), "count": len(filtered)}
        return {"status": "ok", "text": "(no matching directives in collection)", "count": 0}

    if mode == "path":
        filtered = _filter_composite(directives)
        if filtered:
            return {"status": "ok", "text": _render_text(filtered, lang), "count": len(filtered)}
        return {"status": "ok", "text": "(no registered paths)", "count": 0}

    # ── 兜底：关键词搜索 ──
    results = _keyword_search(directives, mode)
    if results:
        return {"status": "ok", "text": _render_text(results, lang), "count": len(results)}
    return {"status": "ok", "text": f"no directives matching \"{mode}\"", "count": 0}
