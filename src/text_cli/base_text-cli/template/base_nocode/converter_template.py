"""
converter_template.py — Turn structured Markdown into a text-cli directive service.

Usage:
    python converter_template.py <experience-doc.md>

    Starts an HTTP server that:
    1. Parses the Markdown doc — extracting domain/action/triggers/entries
    2. Registers text-cli directive handlers
    3. Serves on http://localhost:8000/text-cli/cli

Callers (human or AI):
    curl -X POST http://localhost:8000/text-cli/cli \
      -H "Content-Type: application/json" \
      -d '{"prompt": "AI:<domain>;<action>,<params>"}'

    Or use A0 SDK / textcli-loader / A1 Skill to consume it.

Customization:
    Modify 3 marked sections below — [Custom 1/3] [Custom 2/3] [Custom 3/3].
    Everything else (HTTP server, parsing engine) stays untouched.

    You can also hand this file + your Markdown to an AI and say:
    "Fill in the 3 custom sections for me."

Endpoints:
    POST /text-cli/cli          — Execute directive (SPEC §1.2.1)
    GET  /text-cli/schema       — Package schema (SPEC §3)
    GET  /text-cli/health       — Health check (SPEC §1.2.5)
    POST /text-cli/cli          — AI:text-cli;query → same as GET /text-cli/schema

Markdown format:
    ## Directive (or ## 指令定义)
    - Domain: <domain>
    - Action: <action>
    - Triggers: <keywords>
    - Params: <params>
    - Source: <provenance>          # Optional — knowledge provenance
    - Verified: <who>,<YYYY-MM-DD>  # Optional — verification record
    - Stale After: <YYYY-MM-DD>     # Optional — freshness deadline
    - Status: <draft|stable|deprecated>  # Optional — doc lifecycle (default: stable)

    ## Knowledge (or ## 经验内容)
    ### <category>
    #### <sub-category>
    Content lines...
    Convention fields inside content: 鉴别 (differential diagnosis), 教训 (lessons learned)
"""

import json
import re
import sys
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer


# ═══════════════════════════════════════════════════════
# CHANGE THESE — everything downstream follows
# ═══════════════════════════════════════════════════════

Domain = "your-domain"   # Set your domain (leave "your-domain" to auto-detect from Markdown)
Action = "your-action"   # Set your action (leave "your-action" to auto-detect from Markdown)
Host = "0.0.0.0"         # Bind address
Port = 8000              # Listen port
AuthEnabled = False      # Enable token auth (True/False)
ServiceToken = ""        # Token value (required when AuthEnabled=True)


# ═══════════════════════════════════════════════════════
# [Custom 1/3] — Directive registration
# ═══════════════════════════════════════════════════════

REGISTRY = {}

def register(domain, action, category="knowledge", trust="community", version="0.1.0"):
    """Decorator: register a text-cli directive handler."""
    def decorator(func):
        key = f"{domain};{action}"
        REGISTRY[key] = {
            "func": func,
            "domain": domain,
            "action": action,
            "category": category,
            "trust": trust,
            "version": version,
        }
        return func
    return decorator


# ═══════════════════════════════════════════════════════
# [Custom 2/3] — Markdown parsing logic
# ═══════════════════════════════════════════════════════

# ── Language configuration ────────────────────────────────────────────────
# Field labels that the parser looks for in `## Directive`.
# Each language maps internal keys to the labels used in Markdown.
# Default: zh + en. To add a language (e.g. ja), add one subtree —
# the parsing loop below automatically picks up all labels from all languages.
# Ajouter une langue = ajouter une entrée. Aucun autre changement nécessaire.

FIELD_LABELS = {
    "en": {
        "domain":       "Domain",
        "action":       "Action",
        "triggers":     "Triggers",
        "params":       "Params",
        "source":       "Source",
        "verified":     "Verified",
        "stale_after":  "Stale After",
        "doc_status":   "Status",
    },
    # "fr": {
    #     "domain":       "Domaine",
    #     "action":       "Action",
    #     "triggers":     "Déclencheurs",
    #     "params":       "Paramètres",
    #     "source":       "Source",
    #     "verified":     "Vérifié",
    #     "stale_after":  "Périmé après",
    #     "doc_status":   "Statut",
    # },
    "zh": {
        "domain":       "领域",
        "action":       "动作",
        "triggers":     "触发词",
        "params":       "参数",
        "source":       "来源",
        "verified":     "核实",
        "stale_after":  "过期",
        "doc_status":   "状态",
    }
}

# ── Build flat lookup: label → internal key (all languages merged) ────────
_LABEL_TO_KEY: dict[str, str] = {}
for _lang_labels in FIELD_LABELS.values():
    for _key, _label in _lang_labels.items():
        _LABEL_TO_KEY[_label] = _key

# ── Section headers (also language-configurable) ──────────────────────────
# Ajouter un en-tête de section dans votre langue ici.
_SECTION_DIRECTIVE = ["Directive", "指令定义", "指令定義"]
_SECTION_KNOWLEDGE = ["Knowledge", "经验内容", "経験内容"]


def parse_md(path: str) -> dict:
    """
    Parse a structured Markdown experience document.
    Returns: {"meta": {...}, "entries": [...]}

    Language-agnostic: field labels are driven by FIELD_LABELS above.
    Add a language subtree to support field names in that language.
    Section headers are driven by _SECTION_DIRECTIVE / _SECTION_KNOWLEDGE.
    """
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    # --- Parse meta: match any registered section header ---
    meta = {}
    directive_pattern = r"## (?:" + "|".join(_SECTION_DIRECTIVE) + r")\s*\n(.*?)(?=\n## |\Z)"
    meta_match = re.search(directive_pattern, text, re.DOTALL)
    if meta_match:
        block = meta_match.group(1)
        for label, key in _LABEL_TO_KEY.items():
            pattern = r"[-*]\s*" + re.escape(label) + r"[：:]\s*(.+)"
            m = re.search(pattern, block)
            if m:
                val = m.group(1).strip()
                if key == "triggers":
                    meta[key] = [w.strip() for w in val.replace("，", ",").split(",") if w.strip()]
                elif key == "params":
                    meta[key] = [p.strip() for p in val.replace("，", ",").split(",") if p.strip()]
                else:
                    meta[key] = val

    # --- Parse entries: match any registered knowledge section header ---
    entries = []
    content_start = -1
    for header in _SECTION_KNOWLEDGE:
        idx = text.find(f"## {header}")
        if idx != -1:
            content_start = idx
            break

    if content_start == -1:
        return {"meta": meta, "entries": entries}

    content_text = text[content_start:]

    # Split by ### (H3) — category level
    sections = re.split(r"\n### (.+)", content_text)
    current_category = None
    for i, part in enumerate(sections):
        if i == 0:
            continue
        if i % 2 == 1:
            current_category = part.strip()
        else:
            if current_category:
                # Split by #### (H4) — sub-category level
                subs = re.split(r"\n#### (.+)", part)
                current_sub = None
                for j, sp in enumerate(subs):
                    if j == 0 and sp.strip():
                        # Category overview (no specific sub)
                        pass
                    elif j % 2 == 1:
                        current_sub = sp.strip()
                    else:
                        if current_sub and sp.strip():
                            entries.append({
                                "category": current_category,
                                "sub": current_sub,
                                "content": sp.strip(),
                            })

    return {"meta": meta, "entries": entries}


# ═══════════════════════════════════════════════════════
# Knowledge base (populated after parsing)
# ═══════════════════════════════════════════════════════

_knowledge_base: list[dict] = []
_meta: dict = {}


# ═══════════════════════════════════════════════════════
# [Custom 3/3] — Directive handler + search logic
# ═══════════════════════════════════════════════════════

# Domain/Action priority: user-set value → Markdown-parsed value.
# "your-domain" / "your-action" are sentinels meaning "auto-detect from Markdown".
# Registration is deferred to __main__ (see resolve block below).

def handler(params: list[str]) -> dict:
    """
    Directive format: AI:{Domain};{Action},<category>,<sub>

    Returns dict (rst_data): {"status": "ok", "category": ..., "sub": ..., "content": ...}
    status is tc protocol semantic (§1.2.2) — "ok" on success.
    category/sub/content are parse_md entry fields, returned as-is.
    Trust fields (source/verified/stale_after/doc_status) live in schema, not here.
    """
    if not params:
        return _list_all_dict()

    category = params[0]
    sub = params[1] if len(params) > 1 else ""

    if sub:
        result = _search(category, sub)
        if result:
            return _build_response(category, sub, result["content"])
        results = _search_by_category(category)
        if results:
            return _build_fallback_response(category, results)
        return _not_found_response(category)

    results = _search_by_category(category)
    if results:
        return _build_list_response(category, results)
    return _not_found_response(category)


def _search(category: str, sub: str) -> dict | None:
    """Match by category and sub-category (substring match)."""
    for entry in _knowledge_base:
        if category in entry["category"] and sub in entry["sub"]:
            return entry
    return None


def _search_by_category(category: str) -> list[dict]:
    """Find all entries under a category."""
    return [e for e in _knowledge_base if category in e["category"]]


def _list_categories() -> list[str]:
    cats = sorted({e["category"] for e in _knowledge_base})
    return cats


# ── Response builders (all return dict → rst_data) ──

def _build_response(category: str, sub: str, content: str) -> dict:
    """Exact match: category + sub found."""
    return {"status": "ok", "category": category, "sub": sub, "content": content}


def _build_fallback_response(category: str, entries: list[dict]) -> dict:
    """Sub not matched — return all entries under category."""
    return {
        "status": "ok",
        "category": category,
        "sub": None,
        "items": [{"sub": e["sub"], "content": e["content"]} for e in entries],
    }


def _build_list_response(category: str, entries: list[dict]) -> dict:
    """No sub param — list all subs under category."""
    return {
        "status": "ok",
        "category": category,
        "subs": [e["sub"] for e in entries],
    }


def _list_all_dict() -> dict:
    """No params — list all categories."""
    return {
        "status": "ok",
        "entry_count": len(_knowledge_base),
        "categories": _list_categories(),
    }


def _not_found_response(category: str) -> dict:
    """Category not found."""
    return {
        "status": "ok",
        "category": category,
        "error": f"No results for '{category}'.",
        "available": _list_categories(),
    }


# ═══════════════════════════════════════════════════════
# HTTP server (no customization needed)
# ═══════════════════════════════════════════════════════

_MINIMAL_SCHEMA_TEMPLATE = {
    "id": "",
    "type": "nocode",
    "name": "",
    "name_zh": "",
    "runtime": "path",
    "version": "0.1.0",
    "category": "knowledge",
    "locales": ["en", "zh"],
    "trust": "community",
    "description": "",
    "description_zh": "",
    "directives": [],
}


def _build_schema() -> dict:
    schema = json.loads(json.dumps(_MINIMAL_SCHEMA_TEMPLATE))
    domain = _meta.get("domain", "unknown")
    action = _meta.get("action", "query")
    name = domain.replace("-", " ").title()
    schema["id"] = f"{domain}-{action}"
    schema["name"] = name
    schema["name_zh"] = name
    schema["description"] = f"Knowledge base for {domain}."
    schema["description_zh"] = f"{domain}知识库。"
    for key in REGISTRY:
        d, a = key.split(";")
        entry = {
            "domain": d,
            "domain_zh": d,
            "action": a,
            "action_zh": a,
            "usage": f"{d};{a},<{_meta.get('params', ['param'])[0]}>",
            "usage_zh": f"{d};{a},<{_meta.get('params', ['参数'])[0]}>",
            "description": f"Query {d} knowledge base.",
            "description_zh": f"查询{d}知识库。",
            "params": _meta.get("params", ["param"]),
        }
        # Trust fields: present only if declared in Markdown.
        # These belong to the knowledge production workflow — they may survive
        # or be stripped during data exchange. Code treats absence as normal.
        for trust_key in ("source", "verified", "stale_after", "doc_status"):
            val = _meta.get(trust_key, "")
            if val:
                entry[trust_key] = val
        schema["directives"].append(entry)
    return schema


class TextCliHandler(BaseHTTPRequestHandler):
    """HTTP handler — references cls.* (injectable by subclasses)."""

    REGISTRY = REGISTRY  # default: module-level; override for instances
    AuthEnabled = AuthEnabled
    ServiceToken = ServiceToken

    def do_POST(self):
        if self.path != "/text-cli/cli":
            self._send_json({}, "ERR_NOT_FOUND")
            return

        # Service-token check (SPEC §1.2.1 — runtime reads Service-token header)
        if self.AuthEnabled and self.ServiceToken:
            token = self.headers.get("Service-token", "")
            if token != self.ServiceToken:
                self._send_json({}, "ACCESS_DENIED")
                return

        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length > 0 else {}
        prompt = body.get("prompt", "")
        if not prompt:
            self._send_json({}, "INVALID_PARAMS")
            return

        # Match AI:<domain>;<action>,<params>
        match = re.match(r"^(?:AI|指令):\s*([^;]+);\s*([^,]+)(?:,(.*))?$", prompt)
        if not match:
            self._send_json({}, "INVALID_PARAMS")
            return

        domain, action = match.group(1).strip(), match.group(2).strip()
        params_str = match.group(3) or ""
        params = [p.strip() for p in params_str.split(",")] if params_str else []

        # Directive discovery: AI:text-cli;query → same as GET /text-cli/schema
        if domain == "text-cli" and action == "query":
            self._send_json(_build_schema())
            return

        key = f"{domain};{action}"
        registry = self.REGISTRY
        if key in registry:
            result = registry[key]["func"](params)
        else:
            # Try domain-level fallback
            result = None
            for info in registry.values():
                if info["domain"] == domain and info["action"] == action:
                    result = info["func"](params)
                    break
            if result is None:
                self._send_json({}, "ERR_NOT_FOUND")
                return

        # Handler returns dict → rst_data directly (SPEC §1.2.2)
        self._send_json(result)

    def do_GET(self):
        if self.path == "/text-cli/health":
            self._send_json({"status": "ok", "version": "0.1.0"})
        elif self.path == "/text-cli/schema":
            self._send_json(_build_schema())
        else:
            self._send_json({}, "ERR_NOT_FOUND")

    def _send_json(self, data, err=""):
        """Wrap response in protocol envelope (SPEC §1.2.2).

        rst_err == ""  → success; non-empty → error code from closed set.
        pray_rst_types in data is promoted to rst_types and stripped from rst_data.
        HTTP 200 always — rst_err is the sole error signal.
        """
        rst_types = "text"
        # pray_rst_types promotion (SPEC §1.2.2)
        if isinstance(data, dict):
            pray = data.pop("pray_rst_types", None)
            if pray and rst_types == "text":
                rst_types = pray
        body = json.dumps({
            "rst_types": rst_types,
            "rst_data": data,
            "rst_err": err,
        }, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass  # silent


# ═══════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════

if __name__ == "__main__":
    # --- Parse command-line arguments ---
    args = sys.argv[1:]
    md_path = None
    port = Port
    host = Host
    i = 0
    while i < len(args):
        if args[i] in ("--port", "-p") and i + 1 < len(args):
            port = int(args[i + 1]); i += 2
        elif args[i] in ("--host", "-h") and i + 1 < len(args):
            host = args[i + 1]; i += 2
        elif not md_path and not args[i].startswith("-"):
            md_path = args[i]; i += 1
        else:
            i += 1

    if not md_path:
        print("Usage: python converter_template.py <experience-doc.md> [--port <N>] [--host <addr>]")
        print("Example: python converter_template.py Bonsai-First-Aid-Manual_en.md --port 9000")
        sys.exit(1)

    if not Path(md_path).exists():
        print(f"File not found: {md_path}")
        sys.exit(1)

    data = parse_md(md_path)
    _meta = data["meta"]
    _knowledge_base = data["entries"]

    # --- Resolve effective Domain / Action ---
    # Priority: user-set value (if not default sentinel) → Markdown-parsed value
    md_domain = _meta.get("domain", "")
    md_action = _meta.get("action", "")
    if Domain == "your-domain" and md_domain:
        Domain = md_domain
    if Action == "your-action" and md_action:
        Action = md_action

    # Re-register handler with resolved Domain/Action
    key = f"{Domain};{Action}"
    REGISTRY[key] = {
        "func": handler,
        "domain": Domain,
        "action": Action,
        "category": "knowledge",
        "trust": "community",
        "version": "0.1.0",
    }

    print(f"[OK] Loaded: {md_path}")
    print(f"   Domain: {_meta.get('domain', '?')}")
    print(f"   Action: {_meta.get('action', '?')}")
    print(f"   Entries: {len(_knowledge_base)}")
    print(f"   Categories: {_list_categories()}")
    print()
    print(f"Server: http://{host}:{port}/text-cli/cli")
    print(f"Schema: http://{host}:{port}/text-cli/schema")
    print(f"Health: http://{host}:{port}/text-cli/health")
    print()

    server = HTTPServer((host, port), TextCliHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()
