"""
converter_template.py — 将结构化 Markdown 经验文档转化为 text-cli 指令服务。

用法:
    python converter_template.py <经验文档.md>

    启动后自动:
    1. 解析文档，提取领域/动作/触发词/经验条目
    2. 注册为 text-cli 指令处理器
    3. 启动 HTTP 服务（默认 localhost:8000）

调用方:
    curl -X POST http://localhost:8000/text-cli/cli \
      -H "Content-Type: application/json" \
      -d '{"prompt": "AI:<domain>;<action>,<参数1>,<参数2>"}'

自定义:
    改三处即可适配你的领域——见下方 [自定义区] 标记。
    也可以把本文档和你的 Markdown 一起交给 AI，让 AI 帮你改。

Markdown 格式要求:
    ## 指令定义
    - 领域: <domain>
    - 动作: <action>
    - 触发词: <keywords>
    - 参数: <params>

    ## 经验内容
    ### <分类>
    #### <子类>
    - 原因/表现/症状: ...
    - 急救/处理: ...
    - 预防: ...
"""

import json
import re
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

# ═══════════════════════════════════════════════
# [自定义区 1/3] — 指令注册
# ═══════════════════════════════════════════════

REGISTRY = {}

def register(domain, action, category="知识库", trust="community", version="0.1.0"):
    """装饰器：注册一个 text-cli 指令处理器。"""
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


# ═══════════════════════════════════════════════
# [自定义区 2/3] — 文档解析
# ═══════════════════════════════════════════════

def parse_experience_md(path: str) -> dict:
    """
    解析结构化 Markdown 经验文档。
    返回: {"meta": {...}, "entries": [...]}

    如果你的 Markdown 层级不同（如 H2 代替 H3），修改这里的正则。
    """
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    # 解析指令元数据
    meta = {}
    meta_match = re.search(r"## 指令定义\s*\n(.*?)(?=\n## |\Z)", text, re.DOTALL)
    if meta_match:
        block = meta_match.group(1)
        for key in ("领域", "动作", "触发词", "参数"):
            m = re.search(rf"[-*]\s*{key}[：:]\s*(.+)", block)
            if m:
                val = m.group(1).strip()
                if key == "触发词":
                    meta[key] = [w.strip() for w in val.replace("，", ",").split(",") if w.strip()]
                elif key == "参数":
                    meta[key] = [p.strip() for p in val.replace("，", ",").split(",") if p.strip()]
                else:
                    meta[key] = val

    # 解析经验条目（默认：### 分类 / #### 子类）
    entries = []
    content_start = text.find("## 经验内容")
    if content_start == -1:
        return {"meta": meta, "entries": entries}

    content_text = text[content_start:]
    sections = re.split(r"\n### (.+)", content_text)
    current_category = None
    for i, part in enumerate(sections):
        if i == 0:
            continue
        if i % 2 == 1:
            current_category = part.strip()
        else:
            if current_category:
                subs = re.split(r"\n#### (.+)", part)
                current_sub = None
                for j, sp in enumerate(subs):
                    if j % 2 == 1:
                        current_sub = sp.strip()
                    else:
                        if current_sub:
                            entries.append({
                                "category": current_category,
                                "sub": current_sub,
                                "content": sp.strip(),
                            })

    return {"meta": meta, "entries": entries}


# ═══════════════════════════════════════════════
# 知识库（模块级，解析后填入）
# ═══════════════════════════════════════════════

_knowledge_base = []
_meta = {}


# ═══════════════════════════════════════════════
# [自定义区 3/3] — 指令处理器 + 检索逻辑
# ═══════════════════════════════════════════════

# 改这里的 domain 和 action 以匹配你的 Markdown「指令定义」
@register(domain="家庭园艺", action="盆栽急救")
def handler(params: list[str]) -> str:
    """
    指令格式: AI:家庭园艺;盆栽急救,<参数1>,<参数2>

    改这里以适配你的参数结构。
    """
    if not params:
        return _list_all()

    category = params[0]   # 第一个参数：分类名（如"绿萝"）
    sub = params[1] if len(params) > 1 else ""  # 第二个参数：子类（如"叶片发黄"）

    if sub:
        result = _search(category, sub)
        if result:
            return _format_answer(category, sub, result)
        results = _search_by_category(category)
        if results:
            return _format_answer(category, "常见问题", results)
        return f"未找到「{category}」的相关经验。已知分类: {_list_categories()}"

    results = _search_by_category(category)
    if results:
        lines = [f"[OK] {category} 常见问题:\n"]
        for r in results:
            lines.append(f"  . {r['sub']}")
        return "".join(lines)
    return f"未找到「{category}」的相关经验。已知分类: {_list_categories()}"


def _search(category: str, sub: str) -> dict | None:
    """精确匹配分类和子类。如果你的参数不同，改这里。"""
    for entry in _knowledge_base:
        if category in entry["category"] and sub in entry["sub"]:
            return entry
    return None


def _search_by_category(category: str) -> list[dict]:
    """查找某分类下的所有条目。"""
    return [e for e in _knowledge_base if category in e["category"]]


def _list_categories() -> str:
    cats = sorted({e["category"] for e in _knowledge_base})
    return "、".join(cats) if cats else "(空)"


def _list_all() -> str:
    return (
        f"[OK] 已收录经验 ({len(_knowledge_base)} 条): {_list_categories()}\n"
        f"用法: AI:<domain>;<action>,<分类>,<子类>"
    )


def _format_answer(category: str, sub: str, entry_or_entries) -> str:
    if isinstance(entry_or_entries, dict):
        entries = [entry_or_entries]
    else:
        entries = entry_or_entries
    lines = [f"[OK] {category} . {sub}\n"]
    for entry in entries:
        lines.append(entry["content"])
        lines.append("")
    return "\n".join(lines).strip()


# ═══════════════════════════════════════════════
# HTTP 服务（不需要改）
# ═══════════════════════════════════════════════

_MINIMAL_SCHEMA_TEMPLATE = {
    "id": "",
    "type": "native",
    "name": "",
    "name_zh": "",
    "runtime": "python",
    "version": "0.1.0",
    "category": "知识库",
    "locales": ["zh"],
    "trust": "community",
    "description": "",
    "description_zh": "",
    "directives": [],
}

def _build_schema() -> dict:
    schema = json.loads(json.dumps(_MINIMAL_SCHEMA_TEMPLATE))
    domain = _meta.get("领域", "未分类")
    action = _meta.get("动作", "查询")
    name_zh = _meta.get("名称", domain)
    schema["id"] = f"{domain}-{action}"
    schema["name"] = name_zh
    schema["name_zh"] = name_zh
    schema["description"] = f"Knowledge base for {domain}."
    schema["description_zh"] = f"{name_zh}知识库。"
    for key in REGISTRY:
        d, a = key.split(";")
        schema["directives"].append({
            "domain": d,
            "domain_zh": _meta.get("领域", d),
            "action": a,
            "action_zh": _meta.get("动作", a),
            "usage": f"{d};{a},<{_meta.get('参数', ['param'])[0]}>",
            "usage_zh": f"{_meta.get('领域', d)};{_meta.get('动作', a)},<{_meta.get('参数', ['参数'])[0]}>",
            "description": f"Query {d} knowledge base.",
            "description_zh": f"查询{d}知识库。",
            "params": _meta.get("参数", ["param"]),
        })
    return schema


class TextCliHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/text-cli/cli":
            self._send_json({"error": "not found"}, 404)
            return

        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length > 0 else {}
        prompt = body.get("prompt", "")
        if not prompt:
            self._send_json({"rst_types": "text", "rst_data": {"text": "missing prompt"}, "rst_err": ""})
            return

        # 匹配 AI:<domain>;<action>,<params>
        match = re.match(r"^AI:\s*([^;]+);\s*([^,]+)(?:,(.*))?$", prompt)
        if not match:
            self._send_json({"rst_types": "text", "rst_data": {"text": "invalid prompt"}, "rst_err": ""})
            return

        domain, action = match.group(1).strip(), match.group(2).strip()
        params_str = match.group(3) or ""
        params = [p.strip() for p in params_str.split(",")] if params_str else []

        # 聚合指令支持
        key = f"{domain};{action}"
        if key in REGISTRY:
            result = REGISTRY[key]["func"](params)
        else:
            # 尝试域级匹配
            result = None
            for info in REGISTRY.values():
                if info["domain"] == domain and info["action"] == action:
                    result = info["func"](params)
                    break
            if result is None:
                result = f"指令未找到: {domain};{action}"

        self._send_json({"rst_types": "text", "rst_data": {"text": str(result)}, "rst_err": ""})

    def do_GET(self):
        if self.path == "/text-cli/health":
            self._send_json({"status": "ok", "version": "0.1.0"})
        elif self.path == "/text-cli/schema":
            self._send_json(_build_schema())
        else:
            self._send_json({"error": "not found"}, 404)

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass  # 静默日志


# ═══════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python converter_template.py <经验文档.md>")
        print("示例: python converter_template.py 盆栽急救手册.md")
        sys.exit(1)

    md_path = sys.argv[1]
    if not Path(md_path).exists():
        print(f"文件不存在: {md_path}")
        sys.exit(1)

    data = parse_experience_md(md_path)
    _meta = data["meta"]
    _knowledge_base = data["entries"]

    print(f"[OK] 已加载: {md_path}")
    print(f"   领域: {_meta.get('领域', '?')}")
    print(f"   动作: {_meta.get('动作', '?')}")
    print(f"   条目: {len(_knowledge_base)} 条经验")
    print(f"   分类: {_list_categories()}")
    print()
    print("服务启动: http://localhost:8000/text-cli/cli")
    print()

    server = HTTPServer(("0.0.0.0", 8000), TextCliHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
        server.server_close()
