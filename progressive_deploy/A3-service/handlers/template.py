"""
Template handler.
template;list — list all available templates
template;use,<id>[,key1=val1,key2=val2,...] — fill template placeholders, output to cache
"""

import json
from pathlib import Path
from core.registry import directive

_TEMPLATES_PATH = Path(__file__).resolve().parent.parent / "config" / "prompt_templates.json"


def _load_templates() -> dict:
    with open(_TEMPLATES_PATH) as f:
        return json.load(f)["templates"]


@directive("template", "list")
def template_list(params: list[str]) -> str:
    """List all available templates."""
    tmpl = _load_templates()
    lines = []
    for tid, entry in tmpl.items():
        lines.append(f"{tid}: {entry['desc']}")
    return "\n".join(lines)


@directive("template", "use")
def template_use(params: list[str]) -> str:
    """template;use,<id>[,key1=val1,key2=val2,...] → filled text → cache"""
    if not params:
        return "Missing param: template ID"

    tid = params[0]
    tmpl = _load_templates()

    if tid not in tmpl:
        avail = ", ".join(tmpl.keys())
        return f"Template not found: {tid}. Available: {avail}"

    text = tmpl[tid]["text"]

    # Parse key=value pairs from params[1:]
    fill = {}
    for p in params[1:]:
        if "=" in p:
            k, v = p.split("=", 1)
            fill[k] = v

    # Fill placeholders; keys not provided stay as-is
    for key, val in fill.items():
        text = text.replace("{" + key + "}", val)

    # Cache output
    from handlers.image import _cache_put
    key = _cache_put(text)

    # Report unfilled placeholders
    unfilled = []
    import re
    for m in re.finditer(r"\{(\w+)\}", text):
        uf = m.group(1)
        if uf not in unfilled:
            unfilled.append(uf)

    result = f"cache:{key}\n{text}"
    if unfilled:
        result += f"\n⚠️ Unfilled: {', '.join(unfilled)}"
    return result
