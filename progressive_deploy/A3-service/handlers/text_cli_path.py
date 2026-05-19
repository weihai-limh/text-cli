"""
text-cli;path — 平台自管理：路径解释器。

读取路径定义文件（JSON），按声明式步骤串联执行指令。
支持两种模式：
  - 执行模式：toolchain 线性串联，delegated/partial 优雅降级
  - 声明模式（--register）：将路径注册为可发现的能力声明

Directives:
    AI:text-cli;path,<路径文件路径>[,<初始输入>]          → 执行路径
    AI:text-cli;path,<路径文件路径>,--register           → 注册路径声明
    AI:text-cli;path,<路径文件路径>,--register,<初始输入> → 声明并执行
    AI:文本指令;路径,<路径文件路径>[,<初始输入>]           → 中文别名

路径文件格式 (JSON):
{
  "id": "photo_analysis",
  "name": "照片分析",
  "name_en": "Photo Analysis",
  "version": "1.0.0",
  "type": "skill",
  "lang": "en",
  "mode": "toolchain",
  "description": "...",
  "description_cn": "...",
  "input_schema": {"type": "string", "description_cn": "图片路径"},
  "output_schema": {"type": "text", "description_cn": "照片摘要"},
  "requires": ["image;info", "image;encode", "AI;vision", "AI;reasoning"],
  "steps": [
    {"directive": "image;info,${input}", "output_as": "metadata"},
    {"directive": "image;encode,${input},1024", "output_as": "encoded"}
  ]
}

变量: ${input} = 初始输入, ${step_name} = 上一步 output_as 的输出

Author: Tide 🌊
"""

from __future__ import annotations

import json
import logging
import os
import pathlib
import re

from core.registry import directive, dispatch, get_registered_directives

logger = logging.getLogger(__name__)
VAR_RE = re.compile(r'\$\{(\w+)\}')

# P1: inline interpolation — {step.field}, {step.field.sub}, {step.field.0.sub}
INLINE_RE = re.compile(r'\{(\w+)\.([\w.]+)\}')

# Path schema output directory
_SCHEMA_DIR = pathlib.Path(__file__).parent / "schema"

# Required fields for path declaration
_REQUIRED_DECLARATION = frozenset({"id", "name", "version", "type", "steps"})

# Accepted path types
_ACCEPTED_TYPES = frozenset({"skill", "pipeline"})

# ── Config paths ─────────────────────────────────
_CONFIG_DIR = pathlib.Path(__file__).parent.parent / "config"
_MESSAGES_EN_PATH = _CONFIG_DIR / "path_messages_en.json"
_MESSAGES_CN_PATH = _CONFIG_DIR / "path_messages_cn.json"

# In-memory cache: (lang, mtime_en, mtime_cn) → messages dict
_messages_cache: dict[str, dict] = {}


def _load_messages(lang: str) -> dict:
    """Load message templates for the given language.

    Always starts from EN (canonical, fallback), then overlays
    lang-specific config for keys that differ.
    Results are cached by (lang, file mtimes) for hot-reload.
    """
    try:
        mtime_en = _MESSAGES_EN_PATH.stat().st_mtime if _MESSAGES_EN_PATH.is_file() else 0
    except OSError:
        mtime_en = 0
    try:
        mtime_cn = _MESSAGES_CN_PATH.stat().st_mtime if _MESSAGES_CN_PATH.is_file() else 0
    except OSError:
        mtime_cn = 0

    cache_key = f"{lang}_{mtime_en}_{mtime_cn}"
    if cache_key in _messages_cache:
        return _messages_cache[cache_key]

    # Base: English (canonical)
    messages = {}
    try:
        if _MESSAGES_EN_PATH.is_file():
            messages = json.loads(_MESSAGES_EN_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load EN messages: %s", e)

    # Overlay: language-specific
    if lang != "en":
        lang_path = _CONFIG_DIR / f"path_messages_{lang}.json"
        try:
            if lang_path.is_file():
                overlay = json.loads(lang_path.read_text(encoding="utf-8"))
                messages.update(overlay)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load %s messages: %s", lang, e)

    _messages_cache[cache_key] = messages
    return messages


def _fmt(key: str, messages: dict, **kwargs) -> str:
    """Format a message template by key.

    Returns the formatted string, or [MISSING:key] as defensive fallback.
    """
    template = messages.get(key)
    if template is None:
        return f"[MISSING:{key}]"
    try:
        return template.format(**kwargs)
    except (KeyError, ValueError) as e:
        return f"[FMT_ERR:{key}] {template} ({e})"


def _resolve_var(text: str, variables: dict[str, str]) -> str:
    """Replace ${var} placeholders with values from variables dict."""
    def _repl(m):
        return variables.get(m.group(1), m.group(0))
    return VAR_RE.sub(_repl, text)


# ── P1: inline interpolation ───────────────────

def _interpolate_params(params: list[str], variables: dict[str, str]) -> list[str]:
    """Replace {step.field} and {step.field.index} in params with JSON values.

    Looks up 'step' in variables (JSON string from previous step),
    parses it, navigates to field (optionally index), and returns the value.
    Unmatched references are left as-is (don't block partial path execution).
    """
    if not params:
        return params

    result = []
    for param in params:
        result.append(INLINE_RE.sub(
            lambda m: _interpolate_match(m, variables), param
        ))
    return result


def _interpolate_match(m, variables: dict[str, str]) -> str:
    """Resolve {step.field.sub...} with arbitrary depth path navigation.

    Path segments support:
      - dict keys (string):  {geo.result.location.lng}
      - array indices (int): {geo.results.0.name}
      - mixed:               {geo.poi_infos.0.location.lat}
    """
    step_name = m.group(1)
    path_str = m.group(2)  # e.g. "result.location.lng" or "coord.0"

    raw = variables.get(step_name, '')
    if not raw:
        return m.group(0)

    try:
        import json as _json
        current = _json.loads(raw)
    except (_json.JSONDecodeError, ValueError):
        return m.group(0)

    # Navigate path segments
    for segment in path_str.split('.'):
        if current is None:
            return m.group(0)
        # Try numeric index for lists
        if isinstance(current, list):
            try:
                current = current[int(segment)]
            except (ValueError, IndexError):
                return m.group(0)
        elif isinstance(current, dict):
            current = current.get(segment)
            if current is None:
                return m.group(0)
        else:
            return m.group(0)

    # Return scalar or stringify
    if isinstance(current, (int, float)):
        return str(current)
    if isinstance(current, str):
        return current
    if isinstance(current, list):
        return ','.join(str(v) for v in current)
    if isinstance(current, dict):
        import json as _json
        return _json.dumps(current, ensure_ascii=False)
    return str(current)


def _parse_directive(raw: str) -> tuple[str, str, list[str]]:
    """Parse 'domain;action,param1,param2' into (domain, action, [params]).

    Supports single-quoted params to protect commas: '{"a":1}'
    """
    d = raw.strip()
    if ':' in d and not d.startswith('AI:'):
        pass
    elif d.startswith('AI:'):
        d = d[3:]

    if ',' in d:
        head, rest = d.split(',', 1)
        params = _split_params(rest)
    else:
        head = d
        params = []

    if ';' in head:
        domain, action = head.split(';', 1)
    else:
        domain = head
        action = ""

    return domain.strip(), action.strip(), params


def _split_params(params_str: str) -> list[str]:
    """Split comma-separated params, respecting single-quoted segments."""
    result = []
    buf = []
    in_quote = False
    for ch in params_str:
        if ch == "'":
            in_quote = not in_quote
            continue  # drop the quote char from output
        if ch == ',' and not in_quote:
            result.append(''.join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    if buf:
        result.append(''.join(buf).strip())
    return result


def _execute_step(step: dict, variables: dict[str, str], step_index: int,
                  messages: dict) -> tuple[str, str, str]:
    """Execute a single step.

    Returns (status, result_text, output_as_key).
    status: "ok" | "error" | "delegated"
    """
    raw_directive = step.get("directive", "")
    if not raw_directive:
        return "error", _fmt("STEP_ERR_NO_DIRECTIVE", messages, i=step_index), ""

    resolved = _resolve_var(raw_directive, variables)
    domain, action, params = _parse_directive(resolved)
    # P1: inline interpolation on params
    params = _interpolate_params(params, variables)

    if not domain:
        return "error", _fmt("STEP_ERR_PARSE", messages,
                            i=step_index, raw=raw_directive, resolved=resolved), ""

    timeout_ms = step.get("timeout")
    try:
        if timeout_ms is not None:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(dispatch, domain, action, params)
                try:
                    result = future.result(timeout=timeout_ms / 1000.0)
                except concurrent.futures.TimeoutError:
                    output_as = step.get("output_as", f"_step{step_index}")
                    return "error", _fmt("STEP_TIMEOUT", messages,
                                        i=step_index,
                                        directive=step.get('directive', '?'),
                                        ms=timeout_ms), output_as
        else:
            result = dispatch(domain, action, params)
    except Exception as e:
        return "error", _fmt("STEP_ERR_EXCEPTION", messages,
                            i=step_index, domain=domain, action=action, e=e), ""

    # "No matching directive" → delegated, not error
    if isinstance(result, str) and result.startswith("No matching directive:"):
        return "delegated", f"{domain};{action}", step.get("output_as", "")

    output_as = step.get("output_as", f"_step{step_index}")

    # L0: detect error in handler response — stop path execution
    if isinstance(result, str):
        try:
            parsed = json.loads(result)
            if isinstance(parsed, dict) and parsed.get("status") == "error":
                reason = parsed.get('reason', 'unknown error')
                return "error", _fmt("STEP_ERR_HANDLER", messages,
                                    i=step_index, domain=domain, action=action,
                                    reason=reason), output_as
        except (json.JSONDecodeError, ValueError):
            pass

    return "ok", result, output_as


def _evaluate_if(if_def: dict, variables: dict[str, str]) -> tuple[bool, str]:
    """Evaluate an 'if' condition against previous step outputs.

    Returns (passed: bool, reason: str).
    Supports single condition, all(), any().
    """
    if if_def is None:
        return True, ""

    # Single condition: {"step": "road", "field": "status", "equals": "ok"}
    if "step" in if_def:
        return _check_condition(if_def, variables)

    # Composite: {"all": [...]} or {"any": [...]}
    if "all" in if_def:
        for cond in if_def["all"]:
            ok, reason = _check_condition(cond, variables)
            if not ok:
                return False, reason
        return True, ""

    if "any" in if_def:
        reasons = []
        for cond in if_def["any"]:
            ok, reason = _check_condition(cond, variables)
            if ok:
                return True, ""
            reasons.append(reason)
        return False, "; ".join(reasons)

    return False, f"unknown if structure: {json.dumps(if_def)}"


def _compute_count(raw: str) -> int:
    """Count elements: JSON array → len(), JSON dict with array values → len(first array)."""
    if not raw:
        return 0
    try:
        obj = json.loads(raw)
        if isinstance(obj, list):
            return len(obj)
        if isinstance(obj, dict):
            for v in obj.values():
                if isinstance(v, list):
                    return len(v)
            # If no list found, count keys
            return len(obj)
    except (json.JSONDecodeError, ValueError):
        return 0


def _compare(actual, op: str, expected) -> bool:
    """Compare actual value against expected using operator.

    Supports: eq, gt, lt, gte, lte, ne.
    Compares numerically if both are numeric, else string comparison.
    """
    try:
        a = float(actual) if actual is not None else 0
        e = float(expected)
        numeric = True
    except (ValueError, TypeError):
        a = str(actual) if actual is not None else ""
        e = str(expected)
        numeric = False

    if op == "eq":
        return a == e if numeric else str(a) == str(e)
    elif op == "gt":
        return a > e
    elif op == "lt":
        return a < e
    elif op == "gte":
        return a >= e
    elif op == "lte":
        return a <= e
    elif op == "ne":
        return a != e if numeric else str(a) != str(e)
    return False


def _check_condition(cond: dict, variables: dict[str, str]) -> tuple[bool, str]:
    """Evaluate a single if condition."""
    step_name = cond.get("step", "")
    field = cond.get("field", "")
    raw = variables.get(step_name, "")

    # Parse step output as JSON to access fields
    try:
        obj = json.loads(raw) if raw else {}
    except (json.JSONDecodeError, ValueError):
        obj = {}

    if not isinstance(obj, dict):
        obj = {}

    val = obj.get(field)

    # Function expressions with comparison operators
    # {"step": "search", "field": "count", "op": "gt", "value": 0}
    if "op" in cond and "value" in cond:
        op = cond["op"]
        expected = cond["value"]

        # Function expressions: apply function to step output, not a specific field
        if field == "count":
            func_val = _compute_count(raw)
        elif field == "size":
            func_val = len(raw) if raw else 0
        elif field == "exists":
            func_val = 1 if (raw and raw.strip()) else 0
        elif field == "distance":
            # Reserved: requires coordinate pair
            return False, "distance function not yet implemented"
        else:
            # Regular field comparison: compare field value from parsed JSON
            actual_val = val if val is not None else 0
            ok = _compare(actual_val, op, expected)
            if not ok:
                return False, f"{step_name}.{field} {op} {expected} (actual: {actual_val})"
            return True, ""

        ok = _compare(func_val, op, expected)
        if not ok:
            return False, f"{step_name}.{field} {op} {expected} (actual: {func_val})"
        return True, ""

    # equals
    if "equals" in cond:
        expected = str(cond["equals"])
        actual = str(val) if val is not None else ""
        ok = actual == expected
        return ok, f"{step_name}.{field} == '{actual}' (expected '{expected}')" if not ok else ""

    # contains
    if "contains" in cond:
        needle = cond["contains"]
        haystack = str(val) if val is not None else ""
        ok = needle in haystack
        return ok, f"'{needle}' not in {step_name}.{field}" if not ok else ""

    # matches
    if "matches" in cond:
        import re as _re
        pattern = cond["matches"]
        haystack = str(val) if val is not None else ""
        ok = bool(_re.search(pattern, haystack))
        return ok, f"pattern '{pattern}' not matched in {step_name}.{field}" if not ok else ""

    # exists
    if "exists" in cond:
        ok = val is not None and val != ""
        return ok, f"{step_name}.{field} does not exist or is empty" if not ok else ""

    return False, f"no operator in condition: {json.dumps(cond)}"


def _references_skipped(directive: str, skipped_outputs: set) -> bool:
    """Check if a directive references any skipped output_as via {name.field} or ${name}."""
    for name in skipped_outputs:
        if f"{{{name}." in directive or f"${{{name}}}" in directive:
            return True
    return False


def _execute_parallel_first_ok(p_steps: list, variables: dict, lines: list,
                                messages: dict, group_i: int, group_step: dict,
                                step_results: list, path_id: str,
                                total_steps: int, format: str):
    """Execute parallel steps with first_ok strategy.

    All steps are submitted concurrently. The first to return ok wins;
    its output is written to the group's output_as. On error/timeout,
    degradation chains within each parallel step run independently.
    """
    import concurrent.futures

    group_output_as = group_step.get("output_as", f"_step{group_i}")
    completed = 0
    last_error = ""

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(p_steps)) as executor:
        futures = {}
        for pi, ps in enumerate(p_steps):
            fut = executor.submit(_execute_step, ps, variables, group_i, messages)
            futures[fut] = (pi, ps)

        for fut in concurrent.futures.as_completed(futures):
            pi, ps = futures[fut]
            ps_id = ps.get("id", f"p{pi}")
            try:
                status, result, out = fut.result()
            except Exception as e:
                status, result = "error", str(e)

            completed += 1

            if status == "ok":
                variables[group_output_as] = result
                lines.append(_fmt("PARALLEL_WIN", messages, id=ps_id))
                short = result[:100] + ("…" if len(result) > 100 else "")
                if short:
                    lines.append(_fmt("PARALLEL_WIN_PREVIEW", messages,
                                    short=short))
                step_results.append({
                    "index": group_i, "id": group_step.get("id", ""),
                    "status": "ok", "output_as": group_output_as,
                    "winner": ps_id,
                })
                # Cancel remaining futures
                for f in futures:
                    f.cancel()
                return
            else:
                last_error = result
                lines.append(f"  [{ps_id}] ✗ {result[:80]}")

    # All failed
    lines.append(_fmt("STEP_ERR", messages,
                    i=group_i, directive="parallel group",
                    reason=f"all {len(p_steps)} steps failed: {last_error[:60]}"))
    step_results.append({
        "index": group_i, "id": group_step.get("id", ""),
        "status": "error", "output_as": group_output_as,
        "reason": "all parallel steps failed",
    })


def _execute_parallel_all(p_steps: list, variables: dict, lines: list,
                           messages: dict, group_i: int, group_step: dict,
                           step_results: list, delegated: list):
    """Execute all parallel steps, collect results.

    Each step writes to its own output_as. All must complete.
    """
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(p_steps)) as executor:
        futures = {}
        for pi, ps in enumerate(p_steps):
            fut = executor.submit(_execute_step, ps, variables, group_i, messages)
            futures[fut] = (pi, ps)

        for fut in concurrent.futures.as_completed(futures):
            pi, ps = futures[fut]
            ps_id = ps.get("id", f"p{pi}")
            ps_out = ps.get("output_as", f"_p{pi}")
            try:
                status, result, _ = fut.result()
            except Exception as e:
                status, result = "error", str(e)

            if status == "ok":
                variables[ps_out] = result
                lines.append(_fmt("PARALLEL_ALL_OK", messages,
                                id=ps_id, output_as=ps_out))
                short = result[:100] + ("…" if len(result) > 100 else "")
                if short:
                    lines.append(f"         └─ {short}")
            elif status == "delegated":
                delegated.append({
                    "step": f"{group_i}.{ps_id}",
                    "directive": result,
                    "output_as": ps_out,
                })
                lines.append(f"  [{ps_id}] ⤴ delegated")
            else:
                lines.append(f"  [{ps_id}] ✗ {result[:80]}")

    step_results.append({
        "index": group_i, "id": group_step.get("id", ""),
        "status": "ok", "output_as": group_step.get("output_as", ""),
    })


def _validate_declaration(path_def: dict, path_file: str, messages: dict) -> tuple[bool, str]:
    """Validate that a path definition has the required declaration fields."""
    missing = [f for f in _REQUIRED_DECLARATION if f not in path_def]
    if missing:
        return False, _fmt("REGISTER_ERR_MISSING_FIELDS", messages,
                          fields=', '.join(missing))

    ptype = path_def.get("type", "")
    if ptype not in _ACCEPTED_TYPES:
        return False, _fmt("REGISTER_ERR_UNSUPPORTED_TYPE", messages, type=ptype)

    mode = path_def.get("mode", "toolchain")
    if mode not in ("toolchain", "parallel"):
        return False, _fmt("REGISTER_ERR_UNSUPPORTED_MODE", messages, mode=mode)

    steps = path_def.get("steps", [])
    if not steps:
        return False, _fmt("LOAD_ERR_NO_STEPS", messages)

    return True, "ok"


def _check_requires(path_def: dict) -> tuple[bool, list[str]]:
    """Check which required directives exist in the current registry.

    Returns (all_available, missing_list).
    """
    registered = get_registered_directives()
    # Flatten: {domain: [actions]} → set of "domain;action"
    available = set()
    for dom, actions in registered.items():
        for act in actions:
            available.add(f"{dom};{act}")

    missing = []
    for req in path_def.get("requires", []):
        if req not in available:
            missing.append(req)

    return len(missing) == 0, missing


def _register_path(path_def: dict, source_file: str, messages: dict) -> tuple[bool, str]:
    """Write path declaration to handlers/schema/path_<id>.json.

    The output format matches instruction package schema.json so query's
    glob auto-discovers it.
    """
    path_id = path_def["id"]
    output = {
        "id": path_id,
        "name": path_def.get("name_en", path_def.get("name", path_id)),
        "name_cn": path_def.get("name", path_id),
        "runtime": "composite",
        "type": path_def.get("type", "skill"),
        "version": path_def.get("version", "0.1.0"),
        "mode": path_def.get("mode", "toolchain"),
        "locales": path_def.get("locales", ["en", "cn"]),
        "description": path_def.get("description", ""),
        "description_cn": path_def.get("description_cn", path_def.get("description", "")),
        "input_schema": path_def.get("input_schema", {"type": "string"}),
        "output_schema": path_def.get("output_schema", {"type": "text"}),
        "requires": path_def.get("requires", []),
        "steps": path_def.get("steps", []),
        "directives": path_def.get("directives", []),
        "source_file": source_file,
    }

    # Write
    schema_path = _SCHEMA_DIR / f"path_{path_id}.json"
    try:
        _SCHEMA_DIR.mkdir(parents=True, exist_ok=True)
        schema_path.write_text(
            json.dumps(output, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as e:
        return False, _fmt("REGISTER_ERR_FAILED", messages, msg=str(e))

    logger.info("Path registered: %s → %s", path_id, schema_path)
    return True, str(schema_path)


def _execute_path(path_def: dict, initial_input: str,
                  messages: dict = None, format: str = "text") -> str:
    """Execute a path definition with delegated/partial support.

    Args:
        path_def: Parsed path JSON.
        initial_input: ${input} value.
        messages: Pre-loaded message templates (optional, loaded if None).
        format: "text" (default) or "json" for structured output.
    """
    if messages is None:
        lang = path_def.get("lang", "en")
        messages = _load_messages(lang)

    steps = path_def.get("steps", [])
    path_name = path_def.get("name", path_def.get("id", "unnamed"))
    path_id = path_def.get("id", "unnamed")
    variables: dict[str, str] = {"input": initial_input}
    delegated: list[dict] = []
    skipped_outputs: set = set()  # output_as keys never produced (if skipped)
    lines = [_fmt("PATH_START", messages, name=path_name)]
    step_results: list[dict] = []

    for i, step in enumerate(steps, 1):
        # L1: check if condition before executing
        if "if" in step:
            ok, reason = _evaluate_if(step["if"], variables)
            if not ok:
                output_as = step.get("output_as", f"_step{i}")
                skipped_outputs.add(output_as)
                lines.append(_fmt("STEP_SKIP", messages,
                                i=i, directive=step.get('directive', '?'),
                                reason=reason))
                step_results.append({
                    "index": i, "id": step.get("id", ""), "status": "skipped",
                    "output_as": output_as, "reason": reason,
                })
                # Check if any subsequent step references this skipped output
                directive_str = step.get('directive', '')
                for later_step in steps[i:]:
                    ld = later_step.get('directive', '')
                    if _references_skipped(ld, skipped_outputs):
                        lines.append(_fmt("BRANCH_NO_MATCH", messages, i=i))
                        if format == "json":
                            return json.dumps({
                                "status": "error",
                                "code": "BRANCH_NO_MATCH",
                                "path_id": path_id,
                                "total_steps": len(steps),
                                "completed_steps": i - 1,
                                "failed_step": i,
                                "failed_step_id": step.get("id", ""),
                                "reason": "no executable branch — all if conditions unmatched",
                                "variables": variables,
                            }, ensure_ascii=False)
                        return "\n".join(lines)
                continue

        # L2: parallel group
        if step.get("mode") == "parallel":
            p_steps = step.get("steps", [])
            if not p_steps:
                lines.append(_fmt("STEP_ERR", messages,
                                i=i, directive="parallel group",
                                reason="no steps in parallel group"))
                continue

            strategy = step.get("strategy", "first_ok")
            lines.append(_fmt("PARALLEL_START", messages, strategy=strategy))

            if strategy == "first_ok":
                _execute_parallel_first_ok(
                    p_steps, variables, lines, messages, i, step,
                    step_results, path_id, len(steps), format,
                )
            elif strategy == "all":
                _execute_parallel_all(
                    p_steps, variables, lines, messages, i, step,
                    step_results, delegated,
                )
            else:
                lines.append(_fmt("STEP_ERR", messages,
                                i=i, directive="parallel group",
                                reason=f"unknown strategy: {strategy}"))
            continue

        status, result, output_as = _execute_step(step, variables, i, messages)

        if status == "ok":
            variables[output_as] = result
            short = result[:100] + ("…" if len(result) > 100 else "")
            lines.append(_fmt("STEP_OK", messages,
                            i=i, directive=step.get('directive', '?'),
                            output_as=output_as))
            if short:
                lines.append(_fmt("STEP_OK_PREVIEW", messages, short=short))
            step_results.append({
                "index": i, "id": step.get("id", ""), "status": "ok",
                "output_as": output_as,
            })

        elif status == "delegated":
            delegated.append({
                "step": i,
                "directive": result,
                "output_as": output_as,
            })
            lines.append(_fmt("STEP_DELEGATED", messages,
                            i=i, directive=step.get('directive', '?')))
            step_results.append({
                "index": i, "id": step.get("id", ""), "status": "delegated",
                "output_as": output_as,
            })

        else:  # error/timeout — try degradation, then circuit break
            # Phase 4: degradation chain
            if "degradation" in step:
                recovered = False
                degrade_steps = step["degradation"]
                main_directive = step.get('directive', '?')

                for di, degrade_step in enumerate(degrade_steps):
                    # Guard: no nested degradation
                    if "degradation" in degrade_step:
                        logger.warning(
                            "Nested degradation rejected for step %s",
                            degrade_step.get("id", f"degrade_{di}"),
                        )
                        continue

                    d_id = degrade_step.get("id", f"degrade_{di}")
                    lines.append(_fmt("DEGRADE_TRY", messages,
                                    i=i, directive=main_directive,
                                    degrade_id=d_id))

                    d_status, d_result, _ = _execute_step(
                        degrade_step, variables, i, messages,
                    )

                    if d_status == "ok":
                        variables[output_as] = d_result
                        lines.append(_fmt("DEGRADE_OK", messages,
                                        degrade_id=d_id))
                        short = d_result[:100] + ("…" if len(d_result) > 100 else "")
                        if short:
                            lines.append(_fmt("STEP_OK_PREVIEW", messages,
                                            short=short))
                        step_results.append({
                            "index": i, "id": step.get("id", ""),
                            "status": "ok", "output_as": output_as,
                            "recovered_by": d_id,
                        })
                        recovered = True
                        break
                    else:
                        # Determine if it was a timeout
                        is_timeout = "⏱" in d_result
                        if is_timeout:
                            lines.append(_fmt("DEGRADE_TIMEOUT", messages,
                                            degrade_id=d_id,
                                            ms=degrade_step.get("timeout", "?")))
                        else:
                            lines.append(_fmt("DEGRADE_FAIL", messages,
                                            degrade_id=d_id, reason=d_result))

                if not recovered:
                    # Determine exhaustion type: last step timeout?
                    last_is_timeout = "⏱" in d_result if degrade_steps else False
                    if last_is_timeout:
                        lines.append(_fmt("DEGRADE_EXHAUSTED_TIMEOUT",
                                        messages, i=i))
                    else:
                        lines.append(_fmt("DEGRADE_EXHAUSTED", messages, i=i))

                    step_results.append({
                        "index": i, "id": step.get("id", ""),
                        "status": "error", "output_as": output_as,
                        "reason": "degradation chain exhausted",
                    })

                    if format == "json":
                        code = "DEGRADE_EXHAUSTED_TIMEOUT" if last_is_timeout else "DEGRADE_EXHAUSTED"
                        return json.dumps({
                            "status": "error",
                            "code": code,
                            "path_id": path_id,
                            "total_steps": len(steps),
                            "completed_steps": i - 1,
                            "failed_step": i,
                            "failed_step_id": step.get("id", ""),
                            "reason": "degradation chain exhausted",
                            "variables": variables,
                        }, ensure_ascii=False)
                    return "\n".join(lines)
                # recovered — continue to next step
                continue

            # No degradation — circuit break (L0)
            lines.append(_fmt("CIRCUIT_BREAK", messages,
                            i=i, total=len(steps),
                            directive=step.get('directive', '?'),
                            reason=result))
            step_results.append({
                "index": i, "id": step.get("id", ""), "status": "error",
                "output_as": output_as, "reason": result,
            })

            if format == "json":
                return json.dumps({
                    "status": "error",
                    "code": "CIRCUIT_BREAK",
                    "path_id": path_id,
                    "total_steps": len(steps),
                    "completed_steps": i - 1,
                    "failed_step": i,
                    "failed_step_id": step.get("id", ""),
                    "reason": result,
                    "variables": variables,
                }, ensure_ascii=False)
            return "\n".join(lines)

    # Build result
    if delegated:
        final = _get_final_output(variables, steps)
        lines.append("")
        lines.append(_fmt("PATH_PARTIAL", messages,
                         done=len(steps) - len(delegated), total=len(steps)))
        lines.append(_fmt("PATH_PARTIAL_DELEGATED", messages,
                         json=json.dumps(delegated, ensure_ascii=False)))
        if final:
            lines.append(_fmt("PATH_PARTIAL_RESULT", messages, final=final))

        if format == "json":
            return json.dumps({
                "status": "partial",
                "code": "PARTIAL",
                "path_id": path_id,
                "total_steps": len(steps),
                "completed_steps": len(steps) - len(delegated),
                "delegated": delegated,
                "variables": variables,
            }, ensure_ascii=False)
        return "\n".join(lines)

    final_output = _get_final_output(variables, steps)
    if format == "json":
        return json.dumps({
            "status": "ok",
            "code": "OK",
            "path_id": path_id,
            "total_steps": len(steps),
            "completed_steps": len(steps),
            "variables": variables,
            "output": final_output,
        }, ensure_ascii=False)

    if final_output.strip():
        lines.append("")
        lines.append(_fmt("PATH_OK_RESULT", messages, final=final_output))
    else:
        lines.append("")
        lines.append(_fmt("PATH_OK", messages))
    return "\n".join(lines)


def _get_final_output(variables: dict[str, str], steps: list[dict]) -> str:
    """Extract the final meaningful output from variables."""
    # Try last named output
    for step in reversed(steps):
        key = step.get("output_as", "")
        if key and key in variables:
            return variables[key]
    return ""


@directive("text-cli", "path")
@directive("文本指令", "路径")
def text_cli_path(params: list[str]) -> str:
    """Execute or register a path definition file.

    Modes:
      AI:text-cli;path,<file>[,<input>]          → execute
      AI:text-cli;path,<file>,--register         → register declaration
      AI:text-cli;path,<file>,--register,<input> → register + execute
    """
    if not params:
        # Load default (EN) messages for usage text
        msgs = _load_messages("en")
        return _fmt("USAGE", msgs)

    path_file = params[0].strip()

    # Detect --register and --json flags
    register = False
    output_format = "text"
    initial_input = ""
    for p in params[1:]:
        ps = p.strip()
        if ps == "--register":
            register = True
        elif ps == "--json":
            output_format = "json"
        else:
            initial_input = ps

    # 1. Load path — by file path or by name
    p = pathlib.Path(path_file)
    if not p.is_file():
        # Name-based discovery: scan $TEXT_CLI_HOME/paths/*.json
        _project = pathlib.Path(os.environ.get("TEXT_CLI_HOME", "/root/text-cli"))
        _paths_dir = _project / "paths"
        if _paths_dir.is_dir():
            for _pf in sorted(_paths_dir.glob("*.json")):
                try:
                    _pd = json.loads(_pf.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    continue
                _names = {_pd.get("id", ""), _pd.get("name", ""), _pd.get("name_cn", "")}
                if path_file in _names:
                    p = _pf
                    break
        if not p.is_file():
            msgs = _load_messages("en")
            return _fmt("LOAD_ERR_NOT_FOUND", msgs, path=path_file)

    try:
        path_def = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        msgs = _load_messages("en")
        return _fmt("LOAD_ERR_PARSE", msgs, e=str(e))

    # Load messages based on path's lang declaration
    lang = path_def.get("lang", "en")
    messages = _load_messages(lang)

    # 2. --register mode
    if register:
        ok, msg = _validate_declaration(path_def, path_file, messages)
        if not ok:
            return _fmt("REGISTER_ERR_VALIDATION", messages, msg=msg)

        all_ok, missing = _check_requires(path_def)
        if not all_ok:
            logger.warning(
                "Path %s requires unavailable directives: %s",
                path_def.get("id", "?"), ", ".join(missing),
            )

        ok, msg = _register_path(path_def, path_file, messages)
        if not ok:
            return msg  # _register_path already formats via messages

        path_id = path_def["id"]
        ver = path_def.get("version", "?")
        ptype = path_def.get("type", "?")
        reqs = path_def.get("requires", [])
        registry_path = msg

        result = (
            _fmt("REGISTER_OK", messages, name=path_def.get('name', path_id), ver=ver) + "\n" +
            _fmt("REGISTER_OK_DETAIL", messages, id=path_id, type=ptype,
                 reqs=', '.join(reqs) if reqs else '(none)') + "\n" +
            _fmt("REGISTER_OK_PATH", messages, path=registry_path)
        )
        if missing:
            result += "\n" + _fmt("REGISTER_WARN_DEPS", messages,
                                 deps=', '.join(missing))
        result += "\n  → text-cli;query can discover this path"

        if not initial_input:
            return result

        # Fall through: register + execute
        result += "\n"

    # 3. Execute path
    mode = path_def.get("mode", "toolchain")
    if mode not in ("toolchain", "parallel"):
        return _fmt("LOAD_ERR_UNSUPPORTED_MODE", messages, mode=mode)

    steps = path_def.get("steps", [])
    if not steps:
        return _fmt("LOAD_ERR_NO_STEPS", messages)

    exec_result = _execute_path(path_def, initial_input,
                               messages=messages, format=output_format)

    if register:
        return result + "\n" + exec_result
    return exec_result
