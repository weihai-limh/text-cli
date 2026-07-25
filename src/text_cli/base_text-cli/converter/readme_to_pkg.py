"""
readme_to_pkg.py — 从结构化 Markdown 生成 nocode 指令包 **脚手架**。
输出 schema.json 模板 + 知识库文件骨架，不含完整业务逻辑。

Usage:
    python readme_to_pkg.py 盆栽急救手册.md [--out ./my-pkg/]

Based on the parsing logic from base_nocode/zh/markdown_converter.py.
Extracted to standalone converter — no runtime dependencies.
拿到骨架后请参考 package-nocode-guide_zh.md 补全业务逻辑。
"""

import argparse
import json
import re
import sys
from pathlib import Path

# ── Step 1: Parse Markdown ─────────────────────────────────

def parse_md(path: str) -> dict:
    """Parse a structured Markdown experience document.

    Supports both Chinese and English section naming:

        ## Directive Definition / 指令定义
        - domain: <name> / 领域: <名称>
        - action: <name> / 动作: <名称>
        - trigger_words: <k1,k2> / 触发词: <词1,词2>
        - params: <p1,p2> / 参数: <参数1,参数2>

        ## Experience Content / 经验内容
        ### entity-name / 实体名
        #### condition / 症状
        - reason: ...
        - treatment: ...
    """
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    # ── Meta extraction ──────────────────────────────
    meta = {}
    meta_match = re.search(
        r"## (?:指令定义|Directive Definition)\s*\n(.*?)(?=\n## |\Z)",
        text, re.DOTALL,
    )
    if meta_match:
        block = meta_match.group(1)
        # Canonical English keys
        key_map = {
            "领域": "domain",    "domain": "domain",
            "动作": "action",    "action": "action",
            "触发词": "trigger_words", "trigger_words": "trigger_words",
            "参数": "params",    "params": "params",
        }
        for label, eng_key in key_map.items():
            m = re.search(rf"[-*]\s*{label}[：:]\s*(.+)", block, re.IGNORECASE)
            if m:
                val = m.group(1).strip()
                if eng_key == "trigger_words":
                    meta[eng_key] = [w.strip() for w in val.replace("，", ",").split(",") if w.strip()]
                elif eng_key == "params":
                    meta[eng_key] = [p.strip() for p in val.replace("，", ",").split(",") if p.strip()]
                else:
                    meta[eng_key] = val

    # ── Entry extraction ─────────────────────────────
    entries = []
    content_match = re.search(
        r"## (?:经验内容|Experience Content)\s*\n",
        text,
    )
    if content_match:
        content_text = text[content_match.end():]
        entity_sections = re.split(r"\n### (.+)", content_text)
        current_entity = None
        for i, part in enumerate(entity_sections):
            if i == 0:
                continue
            if i % 2 == 1:
                current_entity = part.strip()
            else:
                if current_entity:
                    condition_sections = re.split(r"\n#### (.+)", part)
                    current_condition = None
                    for j, sp in enumerate(condition_sections):
                        if j % 2 == 1:
                            current_condition = sp.strip()
                        else:
                            if current_condition and sp.strip():
                                entries.append({
                                    "entity": current_entity,
                                    "condition": current_condition,
                                    "content": sp.strip(),
                                })

    return {"meta": meta, "entries": entries}


# ── ID generation ────────────────────────────────────────

def _safe_id(name: str) -> str:
    return re.sub(r"[^a-z0-9-]", "", name.lower().replace(" ", "-"))


def _safe_domain(raw: str) -> str:
    return _safe_id(raw) or "knowledge"


def _safe_action(raw: str) -> str:
    return _safe_id(raw) or "query"


# ── Schema generation ────────────────────────────────────

def _generate_schema(domain: str, action: str, meta: dict, pkg_name: str) -> str:
    params = meta.get("params", ["keyword1", "keyword2"])
    trigger_words = meta.get("trigger_words", [])
    domain_zh = meta.get("domain", domain)
    action_zh = meta.get("action", action)

    return json.dumps({
        "id": _safe_id(pkg_name),
        "name_zh": pkg_name,
        "runtime": "python",
        "type": "native",
        "category": "knowledge",
        "locales": ["zh", "en"],
        "trust": "community",
        "directives": [{
            "domain": domain,
            "domain_zh": domain_zh,
            "action": action,
            "action_zh": action_zh,
            "usage": f"{domain};{action},{','.join(params)}",
            "usage_zh": f"{domain_zh};{action_zh},{','.join(params)}",
            "description": f"Knowledge base search — {pkg_name}",
            "description_zh": f"知识库检索 — {pkg_name}",
            "params": params,
            "params_desc": {p: "search keyword" for p in params},
            "trigger_words": trigger_words,
        }],
    }, ensure_ascii=False, indent=2)


# ── Handler generation ───────────────────────────────────

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
_HANDLER_TMPL = (_TEMPLATE_DIR / "nocode_handler.py.tmpl").read_text(encoding="utf-8")


def _generate_handler(domain: str, action: str, meta: dict, entries: list[dict],
                      pkg_name: str, source_file: str) -> str:
    """Generate handler.py with knowledge base search."""
    params = meta.get("params", [])
    entity_label = params[0] if params else "entity"
    condition_label = params[1] if len(params) > 1 else "condition"
    entries_json = json.dumps(entries, ensure_ascii=False, indent=4)
    func_name = _safe_id(f"{domain}_{action}").replace("-", "_")

    return _HANDLER_TMPL.format(
        pkg_name=pkg_name, source_file=source_file, entries_json=entries_json,
        domain=domain, action=action, func_name=func_name,
        entity_label=entity_label, condition_label=condition_label,
    )


# ── Main ─────────────────────────────────────────────────

def convert(md_path: str, output_dir: str):
    parsed = parse_md(md_path)
    meta = parsed["meta"]
    entries = parsed["entries"]

    domain = _safe_domain(meta.get("domain", ""))
    action = _safe_action(meta.get("action", ""))
    pkg_name = f"{domain}-{action}" if domain and action else Path(md_path).stem

    if not entries:
        print(f"Warning: No experience entries found in '{md_path}'.")
        print("Expected structure: ## 经验内容 -> ### 实体 -> #### 条件 -> 内容")
        if input("Continue with empty knowledge base? [y/N]: ").lower() != "y":
            sys.exit(0)

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    schema_content = _generate_schema(domain, action, meta, pkg_name)
    (out / "schema.json").write_text(schema_content, encoding="utf-8")

    handler_content = _generate_handler(domain, action, meta, entries, pkg_name, md_path)
    (out / "handler.py").write_text(handler_content, encoding="utf-8")

    print(f"Markdown document: {md_path}")
    print(f"  Domain/Action : {domain};{action}")
    print(f"  Entries       : {len(entries)}")
    print(f"  Output        : {out}/")
    print(f"    schema.json ({len(schema_content)} bytes)")
    print(f"    handler.py  ({len(handler_content)} bytes)")
    print()
    print("Next steps:")
    print(f"  1. Review {out}/handler.py — add/remove entries")
    print("  2. Test with textcli-loader:")
    if entries:
        print(f"     cd {out} && python -c \"from textcli_loader import load_package, execute; load_package('.'); print(execute('AI:{domain};{action},{entries[0]['entity']}')['rst_data']['text'])\"")
    print("  3. Re-run converter if you update the Markdown source")


def main():
    parser = argparse.ArgumentParser(
        description="Convert structured Markdown to text-cli nocode instruction package"
    )
    parser.add_argument("document", help="Path to Markdown experience document")
    parser.add_argument("--out", "-o", default=None,
                        help="Output directory (default: ./<name>/)")
    args = parser.parse_args()

    markdown_path = Path(args.document)
    if not markdown_path.exists():
        print(f"Error: File not found: {args.document}")
        sys.exit(1)

    output_dir = args.out or f"./{_safe_id(markdown_path.stem)}/"
    convert(str(markdown_path.resolve()), output_dir)


if __name__ == "__main__":
    main()
