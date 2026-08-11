"""
path-str handler — string primitives for path pipeline composition.

Pure stdlib. Zero dependencies.
Directives:
    path-str;template,<tmpl>[,k=v,...]  → inline template substitution
    path-str;split,'<str>','<delim>'    → split string into array
    path-str;join,'<arr>','<delim>'     → join array into string

"""

import json
import re

from core.registry import directive

@directive("path-str", "template", domain_alias="路径字符串", action_aliases={"template": "模板"})
def path_str_template(params: list[str]) -> dict:
    if not params:
        return {
            "status": "error",
            "reason": "Usage: path-str;template,<tmpl>[,key=val,...]"
        }

    template = params[0]

    kv = {}
    positional = []
    for p in params[1:]:
        if '=' in p:
            k, v = p.split('=', 1)
            kv[k.strip()] = v.strip()
        else:
            positional.append(p.strip())

    replacements = {}
    for i, val in enumerate(positional):
        replacements[str(i)] = val
    replacements.update(kv)

    def _repl(m):
        key = m.group(1)
        return replacements.get(key, m.group(0))

    result = re.sub(r'\{(\w+)\}', _repl, template)

    return {
        "status": "ok",
        "template": template,
        "result": result,
    }

@directive("path-str", "split", domain_alias="路径字符串", action_aliases={"split": "切分"})
def path_str_split(params: list[str]) -> dict:
    if len(params) < 2:
        return {
            "status": "error",
            "reason": "Usage: path-str;split,'<str>','<delim>'"
        }

    text = params[0]
    delim = params[1]
    parts = [p for p in text.split(delim) if p]

    return {
        "status": "ok",
        "parts": parts,
        "count": len(parts),
    }

@directive("path-str", "join", domain_alias="路径字符串", action_aliases={"join": "合并"})
def path_str_join(params: list[str]) -> dict:
    if len(params) < 2:
        return {
            "status": "error",
            "reason": "Usage: path-str;join,'<json-array>','<delim>'"
        }

    try:
        parts = json.loads(params[0])
    except (json.JSONDecodeError, ValueError):
        return {
            "status": "error",
            "reason": "First argument is not a valid JSON array"
        }

    if not isinstance(parts, list):
        return {
            "status": "error",
            "reason": "First argument must be a JSON array"
        }

    delim = params[1]
    result = delim.join(str(p) for p in parts)

    return {
        "status": "ok",
        "result": result,
    }

def init_path_str_handler():
    pass
