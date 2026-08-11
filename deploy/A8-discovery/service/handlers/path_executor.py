"""
Path execution engine — step execution, parallel groups, degradation chains.

Handles sequential/parallel/conditional/degradation step execution, variable
interpolation, inline JSON field access, and HTTP cross-node dispatch.
All comments and messages are in English.
"""

from __future__ import annotations

import concurrent.futures
import contextvars
import json
import logging
import os
import re
import urllib.error
import urllib.request
from urllib.parse import urlparse

from core.registry import dispatch
from core.parser import parse_directive as _core_parse

logger = logging.getLogger(__name__)

VAR_RE = re.compile(r'\{(\w+)\}')

# P1: inline interpolation — {step.field}, {step.field.0}, {step.field.0.name}, ...
INLINE_RE = re.compile(r'\{(\w+)((?:\.\w+|\.\d+)*)\}')

_LOCAL_URL: str | None = None


# ── P1: variable resolution ──────────────────────

def resolve_var(text: str, variables: dict[str, str]) -> str:
    """Replace {var} placeholders with values from variables dict.

    Undefined variables are replaced with empty string and a WARNING is logged.
    This prevents path execution from breaking when steps produce variables
    asynchronously (e.g., synth-loop T8 results).
    """
    undefined: set[str] = set()

    def _repl(m):
        name = m.group(1)
        if name in variables:
            return variables[name]
        undefined.add(name)
        return ""

    result = VAR_RE.sub(_repl, text)
    if undefined:
        logger.warning("undefined variable: %s", ", ".join(sorted(undefined)))
    return result


def interpolate_params(params: list[str], variables: dict[str, str]) -> list[str]:
    """Replace {step.field} and {step.field.index} in params with JSON values."""
    if not params:
        return params

    result = []
    for param in params:
        result.append(INLINE_RE.sub(
            lambda m: _interpolate_match(m, variables), param
        ))
    return result


def _interpolate_match(m, variables: dict[str, str]) -> str:
    """Resolve a {var.field}, {var.field.0}, {var.field.0.name}, ... match."""
    var_name = m.group(1)
    path_tail = m.group(2)

    raw = variables.get(var_name, '')
    if not raw:
        return m.group(0)

    try:
        obj = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return m.group(0)

    cur = obj
    if not path_tail:
        return raw

    segments = path_tail.lstrip('.').split('.')
    for seg in segments:
        if isinstance(cur, dict):
            cur = cur.get(seg)
        elif isinstance(cur, list) and seg.lstrip('-').isdigit():
            try:
                cur = cur[int(seg)]
            except IndexError:
                return m.group(0)
        else:
            return m.group(0)
        if cur is None:
            return m.group(0)

    if isinstance(cur, bool):
        return str(cur).lower()
    if isinstance(cur, (int, float)):
        return str(cur)
    if isinstance(cur, str):
        return cur
    if isinstance(cur, list):
        return ','.join(str(v) for v in cur)
    if isinstance(cur, dict):
        return json.dumps(cur, ensure_ascii=False)
    return str(cur)


# ── Directive parsing ────────────────────────────

def parse_directive(raw: str) -> tuple[str, str, list[str]]:
    """Parse directive using core parser (inherits MAX_DIRECTIVE_LENGTH)."""
    if not raw.startswith(('AI:', '指令:', 'AI：', '指令：')):
        raw = 'AI:' + raw.lstrip()
    parsed = _core_parse(raw)
    return parsed.domain, parsed.action, parsed.params


def split_params(params_str: str) -> list[str]:
    """Split comma-separated params, respecting single/double-quoted segments."""
    result = []
    buf = []
    quote_char = None
    for ch in params_str:
        if ch in ("'", '"'):
            if quote_char is None:
                quote_char = ch
                if ch == "'":
                    continue
                else:
                    buf.append(ch)
                    continue
            elif quote_char == ch:
                quote_char = None
                if ch == "'":
                    continue
                else:
                    buf.append(ch)
                    continue
            else:
                buf.append(ch)
            continue
        if ch == ',' and quote_char is None:
            result.append(''.join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    if buf:
        result.append(''.join(buf).strip())
    return result


# ── Envelope handling ────────────────────────────

def extract_rst_data(raw: str) -> str:
    """Extract rst_data from envelope as JSON string.

    Supports both new format (rst_data = handler dict) and legacy format
    (rst_data = {"text": "<json_string>"}) for transitional compatibility.
    """
    try:
        o = json.loads(raw)
    except (json.JSONDecodeError, ValueError, TypeError):
        return raw
    if isinstance(o, dict) and "rst_data" in o:
        rd = o["rst_data"]
        if isinstance(rd, dict):
            # Legacy format: rst_data has only a "text" key (old nested envelope)
            if len(rd) == 1 and "text" in rd:
                t = rd["text"]
                return t if isinstance(t, str) else json.dumps(t, ensure_ascii=False)
            # New format: rst_data is the handler's dict directly
            return json.dumps(rd, ensure_ascii=False)
        return json.dumps(rd, ensure_ascii=False)
    return raw


# ── HTTP cross-node dispatch ─────────────────────

def get_local_url() -> str | None:
    """Fetch local text-cli endpoint URL from environment."""
    return "http://localhost:28050/text-cli/cli" if "TEST" in os.environ else os.environ.get("TEXT_CLI_LOCAL_URL")


def http_dispatch(url: str, domain: str, action: str, params: list[str],
                  timeout_ms: int | None = None) -> str:
    """POST a directive to a remote text-cli node via HTTP."""
    if urlparse(url).scheme not in ('http', 'https'):
        raise ValueError(f"Invalid URL scheme for remote dispatch: {url}")

    params_str = ",".join(params)
    prompt = f"AI:{domain};{action},{params_str}"
    body = json.dumps({"prompt": prompt}).encode("utf-8")

    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    timeout_s = (timeout_ms / 1000.0) if timeout_ms is not None else 30

    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            return resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.read().decode("utf-8", errors="replace")
    except Exception:
        raise


# ── Step execution ───────────────────────────────

def execute_step(step: dict, variables: dict[str, str], step_index: int,
                 messages: dict,
                 default_source: str | None = None) -> tuple[str, str, str]:
    """Execute a single step. Returns (status, result_text, output_as_key)."""
    raw_directive = step.get("instruction", "") or step.get("directive", "")
    if step.get("directive") and not step.get("instruction"):
        logger.warning(
            "DEPRECATED: step uses 'directive' instead of 'instruction'"
        )
    if not raw_directive:
        return "error", _fmt("STEP_ERR_NO_DIRECTIVE", messages, i=step_index), ""

    resolved = resolve_var(raw_directive, variables)
    domain, action, params = parse_directive(resolved)
    domain = interpolate_params([domain], variables)[0] if domain else domain
    action = interpolate_params([action], variables)[0] if action else action
    params = interpolate_params(params, variables)

    if not domain:
        return "error", _fmt("STEP_ERR_PARSE", messages,
                             i=step_index, raw=raw_directive, resolved=resolved), ""

    timeout_ms = step.get("timeout")
    source = step.get("source") or default_source
    output_as = step.get("output_as", f"_step{step_index}")

    # source dispatch (HTTP cross-node)
    if source:
        effective_timeout = timeout_ms if timeout_ms is not None else 30000
        try:
            raw = http_dispatch(source, domain, action, params, timeout_ms=effective_timeout)
            result = extract_rst_data(raw)
        except Exception as e:
            return "error", _fmt("STEP_ERR_EXCEPTION", messages,
                                 i=step_index, domain=domain, action=action,
                                 e=str(e)), output_as
    else:
        # local dispatch (includes aggregate)
        try:
            if timeout_ms is not None:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    # Copy ContextVar context so ancestor chain survives thread boundary (R6)
                    import contextvars as _cv
                    _ctx = _cv.copy_context()
                    future = executor.submit(_ctx.run, dispatch, domain, action, params)
                    try:
                        result = extract_rst_data(future.result(timeout=timeout_ms / 1000.0))
                    except concurrent.futures.TimeoutError:
                        future.cancel()
                        return "error", _fmt("STEP_TIMEOUT", messages,
                                             i=step_index,
                                             directive=step.get('instruction') or step.get('directive', '?'),
                                             ms=timeout_ms), output_as
            else:
                result = extract_rst_data(dispatch(domain, action, params))
        except Exception as e:
            return "error", _fmt("STEP_ERR_EXCEPTION", messages,
                                 i=step_index, domain=domain, action=action, e=e), ""

    # "No matching directive" = delegated, not error
    if isinstance(result, str) and result.startswith("No matching directive:"):
        return "delegated", f"{domain};{action}", step.get("output_as", "")

    # L0: detect error in handler response
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


# ── Condition evaluation ─────────────────────────

def evaluate_if(if_def: dict, variables: dict[str, str]) -> tuple[bool, str]:
    """Evaluate an 'if' condition. Returns (passed, reason)."""
    if if_def is None:
        return True, ""

    if isinstance(if_def, str):
        interpolated = interpolate_params([if_def], variables)[0]
        m = re.match(r"^\s*(.+?)\s*(==|!=)\s*(.+?)\s*$", interpolated)
        if m:
            left, op, right = m.group(1).strip(), m.group(2), m.group(3).strip()
            right = right.strip("'\"")
            ok = (left == right) if op == "==" else (left != right)
            reason = "" if ok else f"'{left}' {op} '{right}'"
            return ok, reason
        ok = bool(interpolated.strip())
        return ok, "" if ok else "empty condition"

    if "step" in if_def:
        return check_condition(if_def, variables)

    if "all" in if_def:
        for cond in if_def["all"]:
            ok, reason = check_condition(cond, variables)
            if not ok:
                return False, reason
        return True, ""

    if "any" in if_def:
        reasons = []
        for cond in if_def["any"]:
            ok, reason = check_condition(cond, variables)
            if ok:
                return True, ""
            reasons.append(reason)
        return False, "; ".join(reasons)

    logger.warning("unknown if structure: %s", json.dumps(if_def))
    return False, f"unknown if structure: {json.dumps(if_def)}"


def compute_count(raw: str) -> int:
    """Count elements in step output (array length or dict key count)."""
    if not raw:
        return 0
    try:
        obj = json.loads(raw)
        if isinstance(obj, list):
            return len(obj)
        if isinstance(obj, dict):
            result_val = obj.get("result")
            if isinstance(result_val, list):
                return len(result_val)
            for v in obj.values():
                if isinstance(v, list):
                    return len(v)
            return len(obj)
    except (json.JSONDecodeError, ValueError):
        return 0


def compare(actual, op: str, expected) -> bool:
    """Compare actual vs expected using operator (eq/gt/lt/gte/lte/ne)."""
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
    if op == "gt":
        return a > e
    if op == "lt":
        return a < e
    if op == "gte":
        return a >= e
    if op == "lte":
        return a <= e
    if op == "ne":
        return a != e if numeric else str(a) != str(e)
    return False


def check_condition(cond: dict, variables: dict[str, str]) -> tuple[bool, str]:
    """Evaluate a single condition against step output."""
    step_name = cond.get("step", "")
    field = cond.get("field", "")
    raw = variables.get(step_name, "")

    try:
        obj = json.loads(raw) if raw else {}
    except (json.JSONDecodeError, ValueError):
        obj = {}
    if not isinstance(obj, dict):
        obj = {}

    val = obj.get(field)

    if "op" in cond and "value" in cond:
        op = cond["op"]
        expected = cond["value"]

        if field == "count":
            func_val = compute_count(raw)
        elif field == "size":
            func_val = len(raw) if raw else 0
        elif field == "exists":
            func_val = 1 if (raw and raw.strip()) else 0
        else:
            actual_val = val if val is not None else 0
            ok = compare(actual_val, op, expected)
            if not ok:
                return False, f"{step_name}.{field} {op} {expected} (actual: {actual_val})"
            return True, ""

        ok = compare(func_val, op, expected)
        if not ok:
            return False, f"{step_name}.{field} {op} {expected} (actual: {func_val})"
        return True, ""

    if "equals" in cond:
        expected = str(cond["equals"])
        actual = str(val) if val is not None else ""
        return actual == expected, f"{step_name}.{field} == '{actual}' (expected '{expected}')" if actual != expected else ""

    if "contains" in cond:
        needle = cond["contains"]
        haystack = str(val) if val is not None else ""
        return needle in haystack, f"'{needle}' not in {step_name}.{field}" if needle not in haystack else ""

    if "matches" in cond:
        pattern = cond["matches"]
        haystack = str(val) if val is not None else ""
        return bool(re.search(pattern, haystack)), f"pattern '{pattern}' not matched in {step_name}.{field}" if not re.search(pattern, haystack) else ""

    if "exists" in cond:
        ok = val is not None and val != ""
        return ok, f"{step_name}.{field} does not exist or is empty" if not ok else ""

    return False, f"no operator in condition: {json.dumps(cond)}"


def references_skipped(directive: str, skipped_outputs: set) -> bool:
    """Check if a directive references any skipped output_as."""
    for name in skipped_outputs:
        if f"{{{name}." in directive or f"{{{name}}}" in directive:
            return True
    return False


# ── Parallel execution ───────────────────────────

def execute_parallel_first_ok(p_steps: list, variables: dict, lines: list,
                              messages: dict, group_i: int, group_step: dict,
                              step_results: list, path_id: str,
                              total_steps: int, output_format: str,
                              default_source: str | None = None):
    """Execute parallel steps with first_ok strategy — first success wins."""
    group_output_as = group_step.get("output_as", f"_step{group_i}")
    last_error = ""

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(p_steps), 10)) as executor:
        futures = {}
        for pi, ps in enumerate(p_steps):
            ctx = contextvars.copy_context()
            fut = executor.submit(
                ctx.run, _dispatch_step, ps, variables, group_i, messages,
                default_source=default_source,
            )
            futures[fut] = (pi, ps)

        for fut in concurrent.futures.as_completed(futures):
            pi, ps = futures[fut]
            ps_id = ps.get("id", f"p{pi}")
            try:
                status, result, out = fut.result()
            except Exception as e:
                status, result = "error", str(e)

            if status == "ok":
                variables[group_output_as] = result
                lines.append(_fmt("PARALLEL_WIN", messages, id=ps_id))
                short = result[:100] + ("..." if len(result) > 100 else "")
                if short:
                    lines.append(_fmt("PARALLEL_WIN_PREVIEW", messages, short=short))
                step_results.append({
                    "index": group_i, "id": group_step.get("id", ""),
                    "status": "ok", "output_as": group_output_as,
                    "winner": ps_id,
                })
                for f in futures:
                    f.cancel()
                return
            else:
                last_error = result
                lines.append(f"  [{ps_id}] X {result[:80]}")

    lines.append(_fmt("STEP_ERR", messages,
                      i=group_i, directive="parallel group",
                      reason=f"all {len(p_steps)} steps failed: {last_error[:60]}"))
    step_results.append({
        "index": group_i, "id": group_step.get("id", ""),
        "status": "error", "output_as": group_output_as,
        "reason": "all parallel steps failed",
    })


def execute_parallel_all(p_steps: list, variables: dict, lines: list,
                          messages: dict, group_i: int, group_step: dict,
                          step_results: list, delegated: list,
                          default_source: str | None = None):
    """Execute all parallel steps, collecting each result."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(p_steps), 10)) as executor:
        futures = {}
        for pi, ps in enumerate(p_steps):
            ctx = contextvars.copy_context()
            fut = executor.submit(
                ctx.run, _dispatch_step, ps, variables, group_i, messages,
                default_source=default_source,
            )
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
                lines.append(_fmt("PARALLEL_ALL_OK", messages, id=ps_id, output_as=ps_out))
                short = result[:100] + ("..." if len(result) > 100 else "")
                if short:
                    lines.append(f"         L {short}")
            elif status == "delegated":
                delegated.append({
                    "step": f"{group_i}.{ps_id}",
                    "directive": result,
                    "output_as": ps_out,
                })
                lines.append(f"  [{ps_id}] delegated")
            else:
                lines.append(f"  [{ps_id}] X {result[:80]}")

    step_results.append({
        "index": group_i, "id": group_step.get("id", ""),
        "status": "ok", "output_as": group_step.get("output_as", ""),
    })


# ── Path execution orchestration ─────────────────

# Hard cap for map fanout — absolute ceiling, not configurable via yaml
MAP_HARD_CAP = 1000


def _dispatch_step(step: dict, variables: dict[str, str], step_index: int,
                   messages: dict, default_source: str | None = None,
                   depth: int = 0,
                   lines: list = None, step_results: list = None,
                   path_id: str = "", total_steps: int = 0,
                   output_format: str = "text", delegated: list = None) -> tuple[str, str, str]:
    """Unified step dispatcher: routes by mode to the correct executor.

    depth: nesting depth counter for anti-loop guard (≤2, rejects map-in-map).
    When called from execute_path top-level, orchestration args (lines,
    step_results, path_id, total_steps, output_format, delegated) are provided
    so parallel groups can manage their own per-step tracking.
    """
    mode = step.get("mode", "toolchain")

    if mode == "parallel":
        p_steps = step.get("steps", [])
        if not p_steps:
            return "error", _fmt("STEP_ERR", messages, i=step_index,
                                 directive="parallel group",
                                 reason="no steps in parallel group"), ""
        strategy = step.get("strategy", "first_ok")
        if lines is not None:
            lines.append(_fmt("PARALLEL_START", messages, strategy=strategy))
        if strategy == "first_ok":
            execute_parallel_first_ok(
                p_steps, variables, lines or [], messages, step_index, step,
                step_results or [], path_id, total_steps, output_format,
                default_source=default_source,
            )
        elif strategy == "all":
            execute_parallel_all(
                p_steps, variables, lines or [], messages, step_index, step,
                step_results or [], delegated or [],
                default_source=default_source,
            )
        else:
            return "error", _fmt("STEP_ERR", messages, i=step_index,
                                 directive="parallel group",
                                 reason=f"unknown strategy: {strategy}"), ""
        return "ok", "", step.get("output_as", f"_step{step_index}")

    if mode == "map":
        # Anti-nesting guard: depth ≤ 2 (allows map→parallel, rejects map→parallel→map)
        if depth >= 2:
            return "error", _fmt("STEP_ERR", messages, i=step_index,
                                 directive="mode:map",
                                 reason="nested map not allowed (depth limit 2)"), ""
        return _execute_map(step, variables, step_index, messages,
                            default_source=default_source, depth=depth)

    # Default: toolchain (single instruction step)
    return execute_step(step, variables, step_index, messages,
                        default_source=default_source)


# Map config cache — lazy-loaded once per process lifetime
_map_config_cache: tuple | None = None


def _get_map_config() -> tuple:
    """Lazy load map config with graceful degradation (follows A3 guard pattern)."""
    global _map_config_cache
    if _map_config_cache is not None:
        return _map_config_cache
    try:
        from core.config import load_config
        config = load_config()
        _map_config_cache = (
            config.get("paths", {}).get("map_enabled", False),
            config.get("paths", {}).get("map_max_iter", 100),
        )
    except Exception:
        _map_config_cache = (False, 100)
    return _map_config_cache


def _execute_map(step: dict, variables: dict[str, str], step_index: int,
                 messages: dict, default_source: str | None = None,
                 depth: int = 0) -> tuple[str, str, str]:
    """Execute mode:'map' — iterate over items, run sub-steps per element.

    Args:
        depth: current nesting depth (incremented per map level for anti-loop guard).
    """
    import copy as _copy

    map_enabled, map_max_iter_cfg = _get_map_config()
    if not map_enabled:
        return "error", _fmt("STEP_ERR", messages, i=step_index,
                             directive="mode:map",
                             reason="map_disabled"), ""

    items_var = step.get("items", "")
    if not items_var:
        return "error", _fmt("STEP_ERR", messages, i=step_index,
                             directive="mode:map",
                             reason="missing 'items' field"), ""

    raw = variables.get(items_var, "")
    if not raw:
        # Empty items → 0 iterations, collect empty list
        output_as = step.get("output_as", f"_step{step_index}")
        collect_as = step.get("collect_as", output_as)
        variables[collect_as] = "[]"
        return "ok", "[]", output_as

    try:
        items = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return "error", _fmt("STEP_ERR", messages, i=step_index,
                             directive="mode:map",
                             reason=f"items '{items_var}' is not valid JSON"), ""

    if not isinstance(items, list):
        return "error", _fmt("STEP_ERR", messages, i=step_index,
                             directive="mode:map",
                             reason=f"items '{items_var}' is not a list"), ""

    # Fan-out guard
    effective_max = min(map_max_iter_cfg, MAP_HARD_CAP)
    if len(items) > effective_max:
        return "error", _fmt("STEP_ERR", messages, i=step_index,
                             directive="mode:map",
                             reason=f"LOOP_LIMIT: {len(items)} > {effective_max}"), ""

    element_as = step.get("as", "item")
    body_steps = step.get("steps", [])
    on_error = step.get("on_error", "break")
    concurrency = step.get("concurrency", "serial")
    output_as = step.get("output_as", f"_step{step_index}")
    collect_as = step.get("collect_as", output_as)

    collected = []
    skipped = 0

    if concurrency == "parallel":
        # Parallel fan-out per element
        import concurrent.futures as _cf

        def _run_element(idx: int, element):
            v = _copy.deepcopy(variables)
            v[element_as] = json.dumps(element) if not isinstance(element, str) else element
            for bs in body_steps:
                # Recursive dispatch with depth+1 for anti-nesting guard
                s, r, o = _dispatch_step(bs, v, idx, messages,
                                         default_source=default_source,
                                         depth=depth + 1)
                if s == "ok":
                    v[o] = r
                elif s == "error":
                    return ("error", r if on_error == "break" else None)
            # Collect last step's output
            last_out = body_steps[-1].get("output_as", "")
            return ("ok", v.get(last_out, "")) if last_out else ("ok", "")

        with _cf.ThreadPoolExecutor(max_workers=min(len(items), 10)) as executor:
            _map_ctx = contextvars.copy_context()
            futures = {executor.submit(_map_ctx.run, _run_element, i + 1, el): i for i, el in enumerate(items)}
            for fut in _cf.as_completed(futures):
                try:
                    status, val = fut.result()
                except Exception:
                    status, val = "error", str(Exception)
                if status == "ok":
                    collected.append(val)
                else:
                    skipped += 1
                    if on_error == "break":
                        for f in futures:
                            f.cancel()
                        return "error", _fmt("STEP_ERR", messages, i=step_index,
                                             directive="mode:map",
                                             reason=f"element failed (skipped={skipped})"), ""
    else:
        # Serial execution per element
        for idx, element in enumerate(items, 1):
            v = _copy.deepcopy(variables)
            v[element_as] = json.dumps(element) if not isinstance(element, str) else element
            last_val = ""
            last_out = ""
            for bs in body_steps:
                s, r, o = _dispatch_step(bs, v, idx, messages,
                                         default_source=default_source,
                                         depth=depth + 1)
                if s == "ok":
                    v[o] = r
                    last_val = r
                    last_out = o
                elif s == "error":
                    if on_error == "break":
                        return "error", _fmt("STEP_ERR", messages, i=step_index,
                                             directive="mode:map",
                                             reason=f"element {idx} failed"), ""
                    else:
                        skipped += 1
                        break  # skip to next element
            else:
                collected.append(last_val)

    variables[collect_as] = json.dumps(collected, ensure_ascii=False)
    info = f"{len(collected)} results"
    if skipped:
        info += f" ({skipped} skipped)"
    return "ok", json.dumps({"count": len(collected), "skipped": skipped,
                             "collect_as": collect_as}), output_as


def execute_path(path_def: dict, initial_input: str,
                 messages: dict = None, output_format: str = "text") -> str:
    """Execute a full path definition with delegation and degradation support."""
    if messages is None:
        from .path_loader import load_messages
        lang = path_def.get("lang", "en")
        messages = load_messages(lang)

    steps = path_def.get("steps", [])
    path_name = path_def.get("name", path_def.get("id", "unnamed"))
    path_id = path_def.get("id", "unnamed")
    variables: dict[str, str] = {"input": initial_input}
    default_source = path_def.get("default_source")
    delegated: list[dict] = []
    skipped_outputs: set = set()
    lines = [_fmt("PATH_START", messages, name=path_name)]
    step_results: list[dict] = []

    for i, step in enumerate(steps, 1):
        # L1: check if condition
        if "if" in step:
            ok, reason = evaluate_if(step["if"], variables)
            if not ok:
                output_as = step.get("output_as", f"_step{i}")
                skipped_outputs.add(output_as)
                lines.append(_fmt("STEP_SKIP", messages, i=i,
                                  directive=step.get('instruction') or step.get('directive', '?'),
                                  reason=reason))
                step_results.append({
                    "index": i, "id": step.get("id", ""), "status": "skipped",
                    "output_as": output_as, "reason": reason,
                })
                for later_step in steps[i:]:
                    ld = later_step.get('instruction', '') or later_step.get('directive', '')
                    if references_skipped(ld, skipped_outputs):
                        lines.append(_fmt("BRANCH_NO_MATCH", messages, i=i))
                        if output_format == "json":
                            return json.dumps({
                                "status": "error", "code": "BRANCH_NO_MATCH",
                                "path_id": path_id, "total_steps": len(steps),
                                "completed_steps": i - 1, "failed_step": i,
                                "failed_step_id": step.get("id", ""),
                                "reason": "no executable branch", "variables": variables,
                            }, ensure_ascii=False)
                        return "\n".join(lines)
                continue

        # L2: unified dispatch — all modes (toolchain/parallel/map) route through _dispatch_step
        status, result, output_as = _dispatch_step(
            step, variables, i, messages,
            default_source=default_source,
            lines=lines, step_results=step_results,
            path_id=path_id, total_steps=len(steps),
            output_format=output_format, delegated=delegated,
        )

        if status == "ok":
            variables[output_as] = result
            short = result[:100] + ("..." if len(result) > 100 else "")
            lines.append(_fmt("STEP_OK", messages, i=i,
                              directive=step.get('instruction') or step.get('directive', '?'),
                              output_as=output_as))
            if short:
                lines.append(_fmt("STEP_OK_PREVIEW", messages, short=short))
            step_results.append({
                "index": i, "id": step.get("id", ""), "status": "ok",
                "output_as": output_as,
            })

        elif status == "delegated":
            delegated.append({"step": i, "directive": result, "output_as": output_as})
            lines.append(_fmt("STEP_DELEGATED", messages, i=i,
                              directive=step.get('instruction') or step.get('directive', '?')))
            step_results.append({
                "index": i, "id": step.get("id", ""), "status": "delegated",
                "output_as": output_as,
            })

        else:  # error — try degradation, then circuit break
            if "degradation" in step:
                recovered = False
                degrade_steps = step["degradation"]
                main_directive = step.get('instruction') or step.get('directive', '?')

                for di, degrade_step in enumerate(degrade_steps):
                    if "degradation" in degrade_step:
                        logger.warning("Nested degradation rejected for step %s",
                                       degrade_step.get("id", f"degrade_{di}"))
                        continue

                    d_id = degrade_step.get("id", f"degrade_{di}")
                    lines.append(_fmt("DEGRADE_TRY", messages, i=i,
                                      directive=main_directive, degrade_id=d_id))

                    d_status, d_result, _ = _dispatch_step(
                        degrade_step, variables, i, messages,
                        default_source=default_source,
                    )

                    if d_status == "ok":
                        variables[output_as] = d_result
                        lines.append(_fmt("DEGRADE_OK", messages, degrade_id=d_id))
                        short = d_result[:100] + ("..." if len(d_result) > 100 else "")
                        if short:
                            lines.append(_fmt("STEP_OK_PREVIEW", messages, short=short))
                        step_results.append({
                            "index": i, "id": step.get("id", ""),
                            "status": "ok", "output_as": output_as,
                            "recovered_by": d_id,
                        })
                        recovered = True
                        break
                    else:
                        is_timeout = "timeout" in d_result.lower()
                        if is_timeout:
                            lines.append(_fmt("DEGRADE_TIMEOUT", messages,
                                              degrade_id=d_id,
                                              ms=degrade_step.get("timeout", "?")))
                        else:
                            lines.append(_fmt("DEGRADE_FAIL", messages,
                                              degrade_id=d_id, reason=d_result))

                if not recovered:
                    last_is_timeout = "timeout" in str(d_result if 'd_result' in dir() else '')
                    if last_is_timeout:
                        lines.append(_fmt("DEGRADE_EXHAUSTED_TIMEOUT", messages, i=i))
                    else:
                        lines.append(_fmt("DEGRADE_EXHAUSTED", messages, i=i))

                    step_results.append({
                        "index": i, "id": step.get("id", ""),
                        "status": "error", "output_as": output_as,
                        "reason": "degradation chain exhausted",
                    })

                    if output_format == "json":
                        code = "DEGRADE_EXHAUSTED_TIMEOUT" if last_is_timeout else "DEGRADE_EXHAUSTED"
                        return json.dumps({
                            "status": "error", "code": code,
                            "path_id": path_id, "total_steps": len(steps),
                            "completed_steps": i - 1, "failed_step": i,
                            "failed_step_id": step.get("id", ""),
                            "reason": "degradation chain exhausted",
                            "variables": variables,
                        }, ensure_ascii=False)
                    return "\n".join(lines)
                continue

            # No degradation — circuit break
            lines.append(_fmt("CIRCUIT_BREAK", messages, i=i, total=len(steps),
                              directive=step.get('instruction') or step.get('directive', '?'),
                              reason=result))
            step_results.append({
                "index": i, "id": step.get("id", ""), "status": "error",
                "output_as": output_as, "reason": result,
            })

            if output_format == "json":
                return json.dumps({
                    "status": "error", "code": "CIRCUIT_BREAK",
                    "path_id": path_id, "total_steps": len(steps),
                    "completed_steps": i - 1, "failed_step": i,
                    "failed_step_id": step.get("id", ""),
                    "reason": result, "variables": variables,
                }, ensure_ascii=False)
            return "\n".join(lines)

    # Build final result
    if delegated:
        final = get_final_output(variables, steps)
        lines.append("")
        lines.append(_fmt("PATH_PARTIAL", messages, done=len(steps) - len(delegated), total=len(steps)))
        lines.append(_fmt("PATH_PARTIAL_DELEGATED", messages,
                          json=json.dumps(delegated, ensure_ascii=False)))
        if final:
            lines.append(_fmt("PATH_PARTIAL_RESULT", messages, final=final))

        if output_format == "json":
            return json.dumps({
                "status": "partial", "code": "PARTIAL",
                "path_id": path_id, "total_steps": len(steps),
                "completed_steps": len(steps) - len(delegated),
                "delegated": delegated, "variables": variables,
            }, ensure_ascii=False)
        return "\n".join(lines)

    final_output = get_final_output(variables, steps)
    if output_format == "json":
        return json.dumps({
            "status": "ok", "code": "OK",
            "path_id": path_id, "total_steps": len(steps),
            "completed_steps": len(steps), "variables": variables,
            "output": final_output,
        }, ensure_ascii=False)

    if final_output.strip():
        lines.append("")
        lines.append(_fmt("PATH_OK_RESULT", messages, final=final_output))
    else:
        lines.append("")
        lines.append(_fmt("PATH_OK", messages))
    return "\n".join(lines)


def get_final_output(variables: dict[str, str], steps: list[dict]) -> str:
    """Extract the final meaningful output from variables."""
    for step in reversed(steps):
        key = step.get("output_as", "")
        if key and key in variables:
            return variables[key]
    return ""


def _fmt(key: str, messages: dict, **kwargs) -> str:
    """Format a message template with keyword arguments."""
    template = messages.get(key, key)
    if kwargs:
        return template.format(**kwargs)
    return template
