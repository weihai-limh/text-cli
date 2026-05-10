"""
模板 handler。
模板;列表 — 列出所有可用模板
模板;使用,<id>[,键1=值1,键2=值2,...] — 使用模板并填充占位符，输出到缓存
"""

import json
from pathlib import Path
from core.registry import directive

_TEMPLATES_PATH = Path(__file__).resolve().parent.parent / "config" / "prompt_templates.json"


def _load_templates() -> dict:
    with open(_TEMPLATES_PATH) as f:
        return json.load(f)["templates"]


@directive("模板", "列表")
def template_list(params: list[str]) -> str:
    """列出所有可用模板"""
    tmpl = _load_templates()
    lines = []
    for tid, entry in tmpl.items():
        lines.append(f"{tid}: {entry['desc']}")
    return "\n".join(lines)


@directive("模板", "使用")
def template_use(params: list[str]) -> str:
    """模板;使用,<id>[,键1=值1,键2=值2,...] → 填充后文本 → cache"""
    if not params:
        return "缺少参数: 模板ID"

    tid = params[0]
    tmpl = _load_templates()

    if tid not in tmpl:
        avail = ", ".join(tmpl.keys())
        return f"模板不存在: {tid}。可用: {avail}"

    text = tmpl[tid]["text"]

    # 从 params[1:] 解析键值对
    fill = {}
    for p in params[1:]:
        if "=" in p:
            k, v = p.split("=", 1)
            fill[k] = v

    # 默认填充：没有传的键保持原样（作为空值），不强行替换
    for key, val in fill.items():
        text = text.replace("{" + key + "}", val)

    # 缓存输出
    from handlers.image import _cache_put
    key = _cache_put(text)

    # 提示未填充的占位符
    unfilled = []
    import re
    for m in re.finditer(r"\{(\w+)\}", text):
        uf = m.group(1)
        if uf not in unfilled:
            unfilled.append(uf)

    result = f"cache:{key}\n{text}"
    if unfilled:
        result += f"\n⚠️ 未填充: {', '.join(unfilled)}"
    return result
