"""
markdown_converter.py — 将结构化 Markdown 经验文档自动转化为 text-cli 指令

这是 cli/ 三步转化法 的完整演示：
  第一步：能力盘点 → 解析 Markdown 文档结构和元数据
  第二步：领域与动作设计 → 从「指令定义」段落提取
  第三步：指令处理器实现 → 自动注册知识检索处理器

用法:
    python markdown_converter.py 盆栽急救手册.md

    启动后自动:
    1. 解析文档，提取领域/动作/触发词/经验条目
    2. 注册为 text-cli 指令处理器
    3. 启动 HTTP 服务

调用方:
    AI:家庭园艺;盆栽急救,绿萝,叶片发黄
    → 返回: 基于文档中绿萝叶片发黄章节的养护建议

参考:
    nocode/README.md — NoCode 使用说明
"""

import re
import sys
from pathlib import Path

from ...python.cli import register, serve


# ─── 第一步：能力盘点（解析 Markdown） ─────────────

def parse_experience_md(path: str) -> dict:
    """
    解析结构化 Markdown 经验文档。

    期望的结构:
        ## 指令定义
        - 领域: <domain>
        - 动作: <action>
        - 触发词: <keywords>
        - 参数: <params>

        ## 经验内容
        ### <植物名>
        #### <症状>
        - 原因/表现/症状: ...
        - 急救/处理: ...
        - 预防: ...

    返回:
        {
            "meta": {"domain": "家庭园艺", "action": "盆栽急救", "trigger_words": [...], "params": [...]},
            "entries": [
                {"plant": "绿萝", "symptom": "叶片发黄",
                 "content": "原因：浇水过多...\n急救：立即停止..."},
                ...
            ]
        }
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

    # 解析经验条目
    entries = []
    content_start = text.find("## 经验内容")
    if content_start == -1:
        return {"meta": meta, "entries": entries}

    content_text = text[content_start:]

    # 按 ### 分割植物
    plant_sections = re.split(r"\n### (.+)", content_text)
    current_plant = None
    for i, part in enumerate(plant_sections):
        if i == 0:
            continue  # 跳过「## 经验内容」标题之前的内容
        if i % 2 == 1:
            current_plant = part.strip()
        else:
            if current_plant:
                # 按 #### 分割症状
                symptom_sections = re.split(r"\n#### (.+)", part)
                current_symptom = None
                for j, sp in enumerate(symptom_sections):
                    if j == 0 and sp.strip():
                        # 植物总述（无具体症状）
                        pass
                    elif j % 2 == 1:
                        current_symptom = sp.strip()
                    else:
                        if current_symptom:
                            entries.append({
                                "plant": current_plant,
                                "symptom": current_symptom,
                                "content": sp.strip(),
                            })

    return {"meta": meta, "entries": entries}


# ─── 第二步：领域与动作设计（从元数据提取） ──────

def extract_domain_action(meta: dict) -> tuple[str, str]:
    """从文档元数据中提取领域和动作。"""
    domain = meta.get("领域", "未分类")
    action = meta.get("动作", "查询")
    return domain, action


# ─── 第三步：指令处理器实现（注册 + 检索） ──────

# 将解析结果存储为模块级变量，供指令处理器使用
_knowledge_base: list[dict] = []
_meta: dict = {}


@register(domain="家庭园艺", action="盆栽急救", category="知识库", trust="community", version="0.1.0")
def plant_firstaid(params: list[str]) -> str:
    """
    盆栽急救指令处理器。

    指令格式: AI:家庭园艺;盆栽急救,<植物名>,<症状>
    """
    if not params:
        return _list_plants()

    plant = params[0]
    symptom = params[1] if len(params) > 1 else ""

    if symptom:
        # 精确匹配：植物 + 症状
        result = _search(plant, symptom)
        if result:
            return _format_answer(plant, symptom, result)
        # 降级：只匹配植物
        results = _search_by_plant(plant)
        if results:
            return _format_answer(plant, "常见问题", results)
        return f"未找到「{plant}」的相关经验。已知植物: {_list_plant_names()}"

    # 只给植物名，返回该植物的所有症状
    results = _search_by_plant(plant)
    if results:
        lines = [f"[OK] {plant} 常见问题:\n"]
        for r in results:
            lines.append(f"  • {r['symptom']}")
        return "".join(lines)

    return f"未找到「{plant}」的相关经验。已知植物: {_list_plant_names()}"


@register(domain="家庭园艺", action="列表", category="知识库", trust="community")
def list_plants(params: list[str]) -> str:
    """列出所有可用植物。"""
    return f"[OK] 已收录植物: {_list_plant_names()}"


# ─── 检索与格式化工具 ─────────────────────────────

def _search(plant: str, symptom: str) -> dict | None:
    """精确匹配植物和症状。"""
    for entry in _knowledge_base:
        if plant in entry["plant"] and symptom in entry["symptom"]:
            return entry
    return None


def _search_by_plant(plant: str) -> list[dict]:
    """查找某植物的所有症状条目。"""
    return [e for e in _knowledge_base if plant in e["plant"]]


def _list_plant_names() -> str:
    """返回已收录的植物名称列表。"""
    plants = sorted(set(e["plant"] for e in _knowledge_base))
    return "、".join(plants) if plants else "(空)"


def _list_plants() -> str:
    """列出所有已收录植物。"""
    return (
        f"[OK] 已收录植物 ({len(_knowledge_base)} 条经验): {_list_plant_names()}\n"
        f"用法: AI:家庭园艺;盆栽急救,植物名,症状\n"
        f"示例: AI:家庭园艺;盆栽急救,绿萝,叶片发黄"
    )


def _format_answer(plant: str, symptom: str, entry_or_entries) -> str:
    """将检索结果格式化为自然回答。"""
    if isinstance(entry_or_entries, dict):
        entries = [entry_or_entries]
    else:
        entries = entry_or_entries

    lines = [f"[OK] {plant} . {symptom}\n"]
    for entry in entries:
        lines.append(entry["content"])
        lines.append("")
    return "\n".join(lines).strip()


# ─── 主入口 ──────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python markdown_converter.py <经验文档.md>")
        print("示例: python markdown_converter.py examples/盆栽急救手册.md")
        sys.exit(1)

    md_path = sys.argv[1]
    if not Path(md_path).exists():
        print(f"文件不存在: {md_path}")
        sys.exit(1)

    # 解析文档
    data = parse_experience_md(md_path)
    _meta = data["meta"]
    _knowledge_base = data["entries"]

    domain, action = extract_domain_action(_meta)
    print(f"[OK] 已加载: {md_path}")
    print(f"   领域: {domain}")
    print(f"   动作: {action}")
    print(f"   条目: {len(_knowledge_base)} 条经验")
    print(f"   植物: {_list_plant_names()}")
    print()

    # 启动服务
    serve(package_id="plant-firstaid")
