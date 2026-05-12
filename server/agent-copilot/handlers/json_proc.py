"""
JSON processing handler mixin — tc_json_processing.

Directives:
  AI:json;query,<source>,<intent>,<limit?>     (alias: json;query, json;查询)
  AI:json;replace,<source>,<path>,<value>       (alias: json;replace, json;替换)

Design:
  - query: dual path — JSONPath expression (fast, no AI) or natural language (keyword match,
    with future AI semantic routing to text-cli-service).
  - replace: pure mechanical, zero AI. JSONPath navigation + value substitution.
  - source auto-detection: file path (.json) → read from disk; inline text → parse as JSON.

JSONPath subset supported:
  $                  → root
  $.key              → object field
  $.key.subkey       → nested field
  $.array[N]         → array by index
  $.key[*]           → wildcard array
  $.key[*].field     → field of each array element
"""

import json
import os
import re
from pathlib import Path
from core import ok, error


# ═══════════════════════════════════════════════════════════════
# Source resolution
# ═══════════════════════════════════════════════════════════════

def resolve_json_source(source: str, workdir: Path) -> tuple[dict | list | None, str | None]:
    """
    Resolve a JSON source string to a parsed object.
    Returns (parsed_data, error_message_or_None).
    - File path (.json suffix or contains no '{' '[') → read from disk relative to workdir
    - Inline JSON (starts with '{' or '[') → json.loads
    """
    s = source.strip()

    # Inline JSON detection
    if s.startswith('{') or s.startswith('['):
        try:
            return json.loads(s), None
        except json.JSONDecodeError as e:
            return None, f'JSON parse error: {e}'

    # File path
    path = Path(s)
    if not path.is_absolute():
        path = workdir / path

    if not path.exists():
        return None, f'File not found: {path}'

    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f), None
    except json.JSONDecodeError as e:
        return None, f'JSON parse error in {path.name}: {e}'
    except PermissionError:
        return None, f'Permission denied: {path}'


# ═══════════════════════════════════════════════════════════════
# JSONPath navigation (subset)
# ═══════════════════════════════════════════════════════════════

def _resolve_path(obj, path: str):
    """
    Resolve a subset JSONPath against obj.
    Returns (resolved_value, error_or_None).
    """
    if not path.startswith('$'):
        return None, f'JSONPath must start with $: {path}'

    current = obj
    if path == '$':
        return current, None

    # Remove leading $ and split
    remaining = path[1:]  # remove $
    segments = re.findall(r'\.([^.[\]]+)|\[(\d+|\*)\]', remaining)

    for segment in segments:
        field, index = segment
        if field:
            # Object field access
            if not isinstance(current, dict):
                return None, f'Cannot access .{field} on non-object at path up to {current}'
            if field not in current:
                return None, f'Field "{field}" not found'
            current = current[field]
        elif index:
            # Array index access
            if not isinstance(current, list):
                return None, f'Cannot access [{index}] on non-array at path up to {current}'
            if index == '*':
                return current, None  # Return the array itself for wildcard
            idx = int(index)
            if idx < 0 or idx >= len(current):
                return None, f'Index {idx} out of range (length {len(current)})'
            current = current[idx]

    return current, None


# ═══════════════════════════════════════════════════════════════
# Keyword-based JSON query (no-AI fallback for natural language)
# ═══════════════════════════════════════════════════════════════

def _keyword_search(obj, query: str, limit: int = 3) -> list[dict]:
    """
    Walk JSON tree and score paths by keyword overlap with query.
    Returns top-N matches as [{path, value, score}, ...].
    """
    query_tokens = set(query.lower().split())

    results = []

    def _walk(node, path_parts):
        if isinstance(node, dict):
            for k, v in node.items():
                # Score this path
                key_tokens = set(k.lower().replace('_', ' ').split())
                score = len(query_tokens & key_tokens)
                if score > 0:
                    results.append({
                        'path': '.'.join(path_parts + [k]),
                        'value': v if not isinstance(v, (dict, list)) else f'<{type(v).__name__}>',
                        'score': score,
                    })
                _walk(v, path_parts + [k])
        elif isinstance(node, list):
            for i, item in enumerate(node):
                _walk(item, path_parts + [f'[{i}]'])

    _walk(obj, [])
    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:limit]


# ═══════════════════════════════════════════════════════════════
# JsonProcHandlers mixin
# ═══════════════════════════════════════════════════════════════

class JsonProcHandlers:
    """AI:json;query / AI:json;replace"""

    @property
    def _json_workdir(self) -> Path:
        """Working directory for resolving relative file paths"""
        return Path(self.config.get('_config_dir',
                    str(Path(__file__).resolve().parent.parent / 'data'))).parent

    # ── AI:json;query ──

    def _handle_ai_json_query(self, params: list) -> dict:
        """AI:json;query (alias: json;query, json;查询),<source>,<intent>,<limit?>

        source: file path (.json) or inline JSON string
        intent: JSONPath expression (e.g. $.ad_info.name) or natural language query
        limit: max results (default 3)
        """
        if len(params) < 2:
            return error('missing_param',
                        'Required: source (JSON file/string), intent (path or natural language)')

        source = params[0]
        intent = params[1]
        limit = int(params[2]) if len(params) > 2 and params[2].strip().isdigit() else 3

        # Resolve source
        data, err = resolve_json_source(source, self._json_workdir)
        if err:
            return error('invalid_source', err)

        # Detect intent type: JSONPath or natural language
        if intent.strip().startswith('$'):
            # JSONPath fast path — deterministic, zero AI
            value, err = _resolve_path(data, intent.strip())
            if err:
                return error('path_error', err)
            return ok(f'Query result for {intent}',
                     intent=intent, path=intent, result=value)

        # Natural language query — keyword match
        results = _keyword_search(data, intent, limit)
        if not results:
            return ok(f'No matches for "{intent}"',
                     intent=intent, matches=[], count=0)

        formatted = [{
            'path': r['path'],
            'value': str(r['value'])[:200],
            'score': r['score'],
        } for r in results]

        return ok(f'Found {len(results)} match(es) for "{intent}"',
                 intent=intent, count=len(results), matches=formatted)

    # ── AI:json;replace ──

    def _handle_ai_json_replace(self, params: list) -> dict:
        """AI:json;replace (alias: json;replace, json;替换),<source>,<path>,<value>

        source: file path (.json) or inline JSON string (file path → read + write back)
        path: JSONPath to target field
        value: replacement value (JSON-parsed if parseable, else string)
        """
        if len(params) < 3:
            return error('missing_param',
                        'Required: source, path, value')

        source = params[0]
        path_str = params[1].strip()
        raw_value = params[2]

        # Resolve source
        data, err = resolve_json_source(source, self._json_workdir)
        if err:
            return error('invalid_source', err)

        is_file = False
        file_path = None
        s = source.strip()
        if not s.startswith('{') and not s.startswith('['):
            file_path = Path(s)
            if not file_path.is_absolute():
                file_path = self._json_workdir / file_path
            is_file = True

        # JSONPath validation
        if not path_str.startswith('$'):
            return error('invalid_path', f'path must start with $: {path_str}')

        # Parse replacement value
        try:
            value = json.loads(raw_value)
        except json.JSONDecodeError:
            value = raw_value  # keep as plain string

        # Navigate to parent and target key
        parent, target_key, is_array_op = _resolve_parent(data, path_str)
        if parent is None:
            return error('path_error', target_key)  # target_key holds error msg

        # Perform replacement
        old_value = None
        if is_array_op and isinstance(target_key, int):
            if not isinstance(parent, list):
                return error('type_error', f'Expected array at path, got {type(parent).__name__}')
            if target_key < 0 or target_key >= len(parent):
                return error('index_error', f'Index {target_key} out of range (length {len(parent)})')
            old_value = parent[target_key]
            parent[target_key] = value
        else:
            if not isinstance(parent, dict):
                return error('type_error', f'Expected object at path, got {type(parent).__name__}')
            if target_key not in parent:
                return error('key_error', f'Key "{target_key}" not found')
            old_value = parent[target_key]
            parent[target_key] = value

        # Write back if file
        if is_file and file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                wrote_to = str(file_path)
            except PermissionError:
                return error('write_error', f'Permission denied: {file_path}')
        else:
            wrote_to = '<inline>'

        return ok(f'Replaced {path_str}',
                 path=path_str,
                 old=str(old_value)[:200] if old_value is not None else None,
                 new=str(value)[:200],
                 wrote_to=wrote_to)


def _resolve_parent(obj, path_str: str) -> tuple:
    """
    Navigate to the parent of the target path.
    Returns (parent, target_key, is_array) or (None, error_msg, False).
    """
    if not path_str.startswith('$'):
        return None, 'Path must start with $', False
    if path_str == '$':
        return None, 'Cannot replace root ($), specify a sub-path', False

    remaining = path_str[1:]
    segments = re.findall(r'\.([^.[\]]+)|\[(\d+|\*)\]', remaining)

    if not segments:
        return None, f'Invalid path: {path_str}', False

    # Navigate to parent (penultimate segment)
    current = obj
    for i, segment in enumerate(segments[:-1]):
        field, index = segment
        if field:
            if not isinstance(current, dict):
                return None, f'Cannot navigate .{field} on non-object', False
            if field not in current:
                return None, f'Field "{field}" not found', False
            current = current[field]
        elif index:
            if not isinstance(current, list):
                return None, f'Cannot navigate [{index}] on non-array', False
            idx = int(index)
            if idx < 0 or idx >= len(current):
                return None, f'Index {idx} out of range', False
            current = current[idx]

    # Last segment is the target
    last_field, last_index = segments[-1]
    if last_field:
        return current, last_field, False
    else:
        return current, int(last_index), True
