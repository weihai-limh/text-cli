"""
json handler — JSON structure primitives for path pipelines.

Pure stdlib. Zero dependencies.
Directives:
    tc-json;validate,'<json>'                → validate JSON
    tc-json;pretty,'<json>'                  → pretty-print
    tc-json;keys,'<json>'                    → list top-level keys
    tc-json;merge,'<json1>','<json2>'        → shallow merge
    tc-json;parse,'<json>','<dot-path>'      → extract value by path
    tc-json;set,'<json>','<dot-path>','<val>' → set value at path
    tc-json;del,'<json>','<dot-path>'        → delete key at path
    tc-json;pick,'<json>','<paths>'          → extract selected paths
    tc-json;split,'<text>'[,<size>][,<overlap>] → text → JSONL file
    tc-json;join,'<path>'[,<field>]          → JSONL file → text file
"""

import json
import os
import re
import time
from pathlib import Path

from core.registry import directive


def _get_cache_dir() -> Path:
    return Path(os.environ.get(
        "TEXT_CLI_MEDIA_DIR",
        str(Path(os.environ.get("TEXT_CLI_HOME", str(Path.home() / "text-cli"))) / "media"),
    ))


def _try_parse_json_value(s: str):
    """Parse value param as JSON if valid, else return raw string."""
    s = s.strip()
    if not s:
        return s
    try:
        return json.loads(s)
    except (json.JSONDecodeError, ValueError):
        return s



@directive("tc-json", "validate", domain_alias="tc-json", action_aliases={"validate": "校验"})
def json_validate(params: list[str]) -> str:
    if not params:
        return json.dumps({"status": "error", "reason": "Usage: tc-json;validate,'<json>'"})
    try:
        json.loads(params[0])
        return json.dumps({"status": "ok", "valid": True})
    except json.JSONDecodeError as e:
        return json.dumps({"status": "ok", "valid": False, "error": str(e)})



@directive("tc-json", "pretty", domain_alias="tc-json", action_aliases={"pretty": "美化"})
def json_pretty(params: list[str]) -> str:
    if not params:
        return json.dumps({"status": "error", "reason": "Usage: tc-json;pretty,'<json>'"})
    try:
        obj = json.loads(params[0])
        return json.dumps({"status": "ok", "result": json.dumps(obj, ensure_ascii=False, indent=2)})
    except json.JSONDecodeError as e:
        return json.dumps({"status": "error", "reason": f"Invalid JSON: {e}"})



@directive("tc-json", "keys", domain_alias="tc-json", action_aliases={"keys": "所有键"})
def json_keys(params: list[str]) -> str:
    if not params:
        return json.dumps({"status": "error", "reason": "Usage: tc-json;keys,'<json>'"})
    try:
        obj = json.loads(params[0])
    except json.JSONDecodeError as e:
        return json.dumps({"status": "error", "reason": f"Invalid JSON: {e}"})
    if not isinstance(obj, dict):
        return json.dumps({"status": "error", "reason": "Input is not a JSON object"})
    return json.dumps({"status": "ok", "keys": list(obj.keys()), "count": len(obj)})



@directive("tc-json", "merge", domain_alias="tc-json", action_aliases={"merge": "合并"})
def json_merge(params: list[str]) -> str:
    if len(params) < 2:
        return json.dumps({"status": "error", "reason": "Usage: tc-json;merge,'<json1>','<json2>'"})
    try:
        obj1 = json.loads(params[0])
        obj2 = json.loads(params[1])
    except json.JSONDecodeError as e:
        return json.dumps({"status": "error", "reason": f"Invalid JSON: {e}"})
    if not isinstance(obj1, dict) or not isinstance(obj2, dict):
        return json.dumps({"status": "error", "reason": "Both arguments must be JSON objects"})
    merged = {**obj1, **obj2}
    return json.dumps({"status": "ok", "result": merged})



def _json_path_get(obj, path: str):
    """Navigate dot-path into JSON structure. Supports array indices."""
    if not path:
        return obj
    parts = path.split(".")
    current = obj
    for part in parts:
        if current is None:
            return None
        if isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return None
        elif isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _json_path_set(obj, path: str, value):
    """Set value at dot-path, creating intermediate dicts."""
    parts = path.split(".")
    current = obj
    for i, part in enumerate(parts[:-1]):
        if isinstance(current, dict):
            if part not in current or not isinstance(current.get(part), dict):
                current[part] = {}
            current = current[part]
        elif isinstance(current, list):
            try:
                idx = int(part)
                while len(current) <= idx:
                    current.append({})
                current = current[idx]
            except (ValueError, IndexError):
                return False
        else:
            return False
    last = parts[-1]
    if isinstance(current, dict):
        current[last] = value
        return True
    elif isinstance(current, list):
        try:
            idx = int(last)
            while len(current) <= idx:
                current.append(None)
            current[idx] = value
            return True
        except (ValueError, IndexError):
            return False
    return False


def _json_path_del(obj, path: str):
    """Delete key at dot-path. Returns True if deleted, False if not found."""
    parts = path.split(".")
    current = obj
    for i, part in enumerate(parts[:-1]):
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return False
        else:
            return False
        if current is None:
            return False
    last = parts[-1]
    if isinstance(current, dict):
        if last in current:
            del current[last]
            return True
    elif isinstance(current, list):
        try:
            idx = int(last)
            if 0 <= idx < len(current):
                del current[idx]
                return True
        except (ValueError, IndexError):
            pass
    return False


@directive("tc-json", "parse", domain_alias="tc-json", action_aliases={"parse": "解析"})
def json_parse(params: list[str]) -> str:
    if len(params) < 2:
        return json.dumps({"status": "error", "reason": "Usage: tc-json;parse,'<json>','<dot-path>'"})
    try:
        obj = json.loads(params[0])
    except json.JSONDecodeError:
        return json.dumps({"status": "error", "reason": "Input is not valid JSON"})
    result = _json_path_get(obj, params[1])
    if result is None:
        return json.dumps({"status": "error", "reason": f"Path '{params[1]}' not found"})
    if isinstance(result, (int, float, str, bool, type(None))):
        return json.dumps({"status": "ok", "value": result})
    return json.dumps({"status": "ok", "value": result})



@directive("tc-json", "set", domain_alias="tc-json", action_aliases={"set": "设置"})
def json_set(params: list[str]) -> str:
    """tc-json;set,'<json>','<dot-path>','<value>' — set value at path."""
    if len(params) < 3:
        return json.dumps({"status": "error", "reason": "Usage: tc-json;set,'<json>','<path>','<value>'"})
    try:
        obj = json.loads(params[0])
    except json.JSONDecodeError:
        return json.dumps({"status": "error", "reason": "Input is not valid JSON"})
    if not isinstance(obj, dict):
        return json.dumps({"status": "error", "reason": "Input must be a JSON object"})
    value = _try_parse_json_value(params[2])
    ok = _json_path_set(obj, params[1], value)
    if not ok:
        return json.dumps({"status": "error", "reason": f"Cannot set path '{params[1]}'"})
    return json.dumps({"status": "ok", "result": obj})



@directive("tc-json", "del", domain_alias="tc-json", action_aliases={"del": "删除"})
def json_del(params: list[str]) -> str:
    """tc-json;del,'<json>','<dot-path>' — delete key at path."""
    if len(params) < 2:
        return json.dumps({"status": "error", "reason": "Usage: tc-json;del,'<json>','<path>'"})
    try:
        obj = json.loads(params[0])
    except json.JSONDecodeError:
        return json.dumps({"status": "error", "reason": "Input is not valid JSON"})
    if not isinstance(obj, dict):
        return json.dumps({"status": "error", "reason": "Input must be a JSON object"})
    ok = _json_path_del(obj, params[1])
    if not ok:
        return json.dumps({"status": "error", "reason": f"Path '{params[1]}' not found or not deletable"})
    return json.dumps({"status": "ok", "result": obj})



@directive("tc-json", "pick", domain_alias="tc-json", action_aliases={"pick": "提取"})
def json_pick(params: list[str]) -> str:
    """tc-json;pick,'<json>','<path1>[,<path2>,...]' — extract selected paths."""
    if len(params) < 2:
        return json.dumps({"status": "error", "reason": "Usage: tc-json;pick,'<json>','<path1>[,<path2>,...]'"})
    try:
        obj = json.loads(params[0])
    except json.JSONDecodeError:
        return json.dumps({"status": "error", "reason": "Input is not valid JSON"})
    if not isinstance(obj, dict):
        return json.dumps({"status": "error", "reason": "Input must be a JSON object"})

    try:
        paths = json.loads(params[1])
        if not isinstance(paths, list):
            raise ValueError("not a list")
    except (json.JSONDecodeError, ValueError):
        return json.dumps({"status": "error", "reason": "Second param must be a JSON array of dot-paths"})
    result = {}
    for path in paths:
        val = _json_path_get(obj, path)
        if val is not None:
            _json_path_set(result, path, val)
    return json.dumps({"status": "ok", "result": result, "count": len(paths)})



SENTENCE_END = re.compile(r'(?<=[。！？\n])')
MIN_CHUNK_LEN = 30


@directive("tc-json", "split", domain_alias="tc-json", action_aliases={"split": "分块"})
def json_split(params: list[str]) -> str:
    """tc-json;split,'<text>'[,<size>][,<overlap>] — text → JSONL file."""
    if not params:
        return json.dumps({"status": "error", "reason": "Usage: tc-json;split,'<text>'[,<size>][,<overlap>]"})

    text = params[0]
    chunk_size = int(params[1]) if len(params) > 1 and params[1] else 5000
    overlap = int(params[2]) if len(params) > 2 and params[2] else 0

    sentences = SENTENCE_END.split(text)
    chunks = []
    current = ""
    for sent in sentences:
        if len(current) + len(sent) > chunk_size and current:
            chunks.append(current.strip())
            if overlap > 0:
                tail = current[-overlap:] if len(current) >= overlap else current
                current = tail + sent
            else:
                current = sent
        else:
            current += sent
    if current.strip():
        chunks.append(current.strip())

    entries = []
    total_chars = 0
    for i, ch in enumerate(chunks):
        if len(ch) < MIN_CHUNK_LEN:
            continue
        total_chars += len(ch)
        entries.append({
            "id": f"chunk_{i+1:04d}",
            "index": i,
            "char_count": len(ch),
            "text": ch,
        })

    cache_dir = _get_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)
    ts = int(time.time() * 1000)
    out_path = cache_dir / f"split_{ts}.jsonl"
    with open(str(out_path), "w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    return json.dumps({
        "status": "ok",
        "path": str(out_path),
        "count": len(entries),
        "total_chars": total_chars,
    })



@directive("tc-json", "join", domain_alias="tc-json", action_aliases={"join": "拼接"})
def json_join(params: list[str]) -> str:
    """tc-json;join,'<path>'[,<field>] — JSONL file → text file."""
    if not params:
        return json.dumps({"status": "error", "reason": "Usage: tc-json;join,'<path>'[,<field>]"})

    src_path = Path(params[0])
    field = params[1] if len(params) > 1 and params[1] else "text"

    if not src_path.exists():
        return json.dumps({"status": "error", "reason": f"File not found: {src_path}"})

    texts = []
    try:
        with open(str(src_path), "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                val = entry.get(field, "")
                if isinstance(val, str):
                    texts.append(val)
                else:
                    texts.append(str(val))
    except json.JSONDecodeError as e:
        return json.dumps({"status": "error", "reason": f"JSON parse error in file: {e}"})
    except Exception as e:
        return json.dumps({"status": "error", "reason": str(e)})

    merged = "\n".join(texts)
    count = len(texts)
    total_chars = len(merged)

    cache_dir = _get_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)
    ts = int(time.time() * 1000)
    out_path = cache_dir / f"join_{ts}.txt"
    out_path.write_text(merged, encoding="utf-8")

    return json.dumps({
        "status": "ok",
        "path": str(out_path),
        "count": count,
        "total_chars": total_chars,
    })


def init_json_handler():
    pass
