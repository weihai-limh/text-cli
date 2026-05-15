"""
text-cli;path — Platform self-management: path interpreter。

读取路径定义文件（JSON），按声明式step串联执行指令。
支持两种模式：
  - Execute mode: toolchain linear chain with graceful delegated/partial degradation
  - Declare mode (--register): register path as discoverable capability declaration

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
import pathlib
import re

from core.registry import directive, dispatch, get_registered_directives

logger = logging.getLogger(__name__)
VAR_RE = re.compile(r'\$\{(\w+)\}')
INLINE_RE = re.compile(r'\{(\w+)\.(\w+)(?:\.(\d+))?\}')

# Path schema output directory
_SCHEMA_DIR = pathlib.Path(__file__).parent / "schema"

# Required fields for path declaration
_REQUIRED_DECLARATION = frozenset({"id", "name", "version", "type", "steps"})

# Accepted path types
_ACCEPTED_TYPES = frozenset({"skill", "pipeline"})


def _resolve_var(text: str, variables: dict[str, str]) -> str:
    """Replace ${var} placeholders with values from variables dict."""
    def _repl(m):
        return variables.get(m.group(1), m.group(0))
    return VAR_RE.sub(_repl, text)


def _split_params(params_str: str) -> list[str]:
    """Split comma-separated params, respecting single-quoted segments."""
    result = []
    buf = []
    in_quote = False
    for ch in params_str:
        if ch == "'":
            in_quote = not in_quote
            continue
        if ch == ',' and not in_quote:
            result.append(''.join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    if buf:
        result.append(''.join(buf).strip())
    return result


def _interpolate_params(params: list[str], variables: dict[str, str]) -> list[str]:
    """Replace {step.field.index} in params with JSON values from step outputs."""
    if not params:
        return params
    result = []
    for param in params:
        result.append(INLINE_RE.sub(
            lambda m: _interpolate_match(m, variables), param
        ))
    return result


def _interpolate_match(m, variables: dict[str, str]) -> str:
    """Resolve a single {step.field.index} match from a step's JSON output."""
    step_name = m.group(1)
    field = m.group(2)
    idx = m.group(3)
    raw = variables.get(step_name, '')
    if not raw:
        return m.group(0)
    try:
        obj = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return m.group(0)
    if not isinstance(obj, dict):
        return m.group(0)
    val = obj.get(field)
    if val is None:
        return m.group(0)
    if idx is not None and isinstance(val, list):
        try:
            val = val[int(idx)]
        except (IndexError, ValueError):
            return m.group(0)
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, str):
        return val
    if isinstance(val, list):
        return ','.join(str(v) for v in val)
    return str(val)


def _parse_directive(raw: str) -> tuple[str, str, list[str]]:
    """Parse 'domain;action,param1,param2' with single-quote support."""
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


def _execute_step(step: dict, variables: dict[str, str], step_index: int) -> tuple[str, str, str]:
    """Execute a single step.

    Returns (status, result_text, output_as_key).
    status: "ok" | "error" | "delegated"
    """
    raw_directive = step.get("directive", "")
    if not raw_directive:
        return "error", f"[step {step_index}] Missing directive field", ""

    resolved = _resolve_var(raw_directive, variables)
    domain, action, params = _parse_directive(resolved)
    # P1: inline interpolation on params
    params = _interpolate_params(params, variables)

    if not domain:
        return "error", f"[step {step_index}] Cannot parse directive: {raw_directive} → {resolved}", ""

    try:
        result = dispatch(domain, action, params)
    except Exception as e:
        return "error", f"[step {step_index}] {domain};{action} execution error: {e}", ""

    # "No matching directive" → delegated, not error
    if isinstance(result, str) and result.startswith("No matching directive:"):
        return "delegated", f"{domain};{action}", step.get("output_as", "")

    output_as = step.get("output_as", f"_step{step_index}")

    # L0: detect handler error response — circuit break
    if isinstance(result, str):
        try:
            parsed = json.loads(result)
            if isinstance(parsed, dict) and parsed.get("status") == "error":
                return "error", f"[step {step_index}] {domain};{action}: {parsed.get('reason', 'unknown error')}", output_as
        except (json.JSONDecodeError, ValueError):
            pass

    return "ok", result, output_as


def _validate_declaration(path_def: dict, path_file: str) -> tuple[bool, str]:
    """Validate that a path definition has the required declaration fields."""
    missing = [f for f in _REQUIRED_DECLARATION if f not in path_def]
    if missing:
        return False, f"Path declaration missing required fields: {', '.join(missing)}"

    ptype = path_def.get("type", "")
    if ptype not in _ACCEPTED_TYPES:
        return False, f"Unsupported path type \"{ptype}\"（仅接受 skill/pipeline）"

    mode = path_def.get("mode", "toolchain")
    if mode != "toolchain":
        return False, f"Unsupported path mode \"{mode}\"（当前仅支持 toolchain）"

    steps = path_def.get("steps", [])
    if not steps:
        return False, "Path definition has no steps"

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


def _register_path(path_def: dict, source_file: str) -> tuple[bool, str]:
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
        return False, f"Write failed: {e}"

    logger.info("Path registered: %s → %s", path_id, schema_path)
    return True, str(schema_path)


def _execute_path(path_def: dict, initial_input: str) -> str:
    """Execute a path definition with delegated/partial support."""
    steps = path_def.get("steps", [])
    path_name = path_def.get("name", path_def.get("id", "unnamed"))
    variables: dict[str, str] = {"input": initial_input}
    delegated: list[dict] = []
    lines = [f"═══ {path_name} ═══"]

    for i, step in enumerate(steps, 1):
        status, result, output_as = _execute_step(step, variables, i)

        if status == "ok":
            variables[output_as] = result
            short = result[:100] + ("…" if len(result) > 100 else "")
            lines.append(f"  [{i}] {step.get('directive', '?')} ✓ ({output_as})")
            if short:
                lines.append(f"      → {short}")

        elif status == "delegated":
            delegated.append({
                "step": i,
                "directive": result,
                "output_as": output_as,
            })
            lines.append(f"  [{i}] {step.get('directive', '?')} ⤴ delegated")

        else:  # error — L0 circuit break
            lines.append(f"  [{i}] {step.get('directive', '?')} ✗ {result}")
            return "\n".join(lines)

    # Build result
    if delegated:
        final = _get_final_output(variables, steps)
        lines.append("")
        lines.append(f"[部分completed] {len(steps) - len(delegated)}/{len(steps)} stepcompleted")
        lines.append(f"[Needs upper-layer handling] {json.dumps(delegated, ensure_ascii=False)}")
        if final:
            lines.append(f"[Current result] {final}")
        return "\n".join(lines)

    final_output = _get_final_output(variables, steps)
    lines.append("")
    lines.append(f"[Result]\n{final_output}" if final_output.strip() else "[completed]")
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
        return (
            "用法:\n"
            "  AI:text-cli;path,<路径文件>[,<初始输入>]          → 执行路径\n"
            "  AI:text-cli;path,<路径文件>,--register           → 注册声明\n"
            "  AI:text-cli;path,<路径文件>,--register,<初始输入> → 声明并执行\n\n"
            "路径文件为声明式 JSON，定义step串联。\n"
            "注册后路径作为 composite 类型指令出现在 text-cli;query 中。"
        )

    path_file = params[0].strip()

    # Detect --register flag
    register = False
    initial_input = ""
    for p in params[1:]:
        ps = p.strip()
        if ps == "--register":
            register = True
        else:
            initial_input = ps

    # 1. Load path file
    p = pathlib.Path(path_file)
    if not p.is_file():
        return f"Path file not found: {path_file}"

    try:
        path_def = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        return f"Path file parse error: {e}"

    # 2. --register mode
    if register:
        ok, msg = _validate_declaration(path_def, path_file)
        if not ok:
            return f"Path declaration validation failed: {msg}"

        all_ok, missing = _check_requires(path_def)
        if not all_ok:
            logger.warning(
                "Path %s requires unavailable directives: %s",
                path_def.get("id", "?"), ", ".join(missing),
            )

        ok, msg = _register_path(path_def, path_file)
        if not ok:
            return f"Path registration failed: {msg}"

        path_id = path_def["id"]
        ver = path_def.get("version", "?")
        ptype = path_def.get("type", "?")
        reqs = path_def.get("requires", [])
        registry_path = msg

        result = (
            f"Path registered: {path_def.get('name', path_id)} (v{ver})\n"
            f"  id: {path_id}\n"
            f"  type: {ptype}\n"
            f"  requires: {', '.join(reqs) if reqs else '(无)'}\n"
            f"  Registry location: {registry_path}"
        )
        if missing:
            result += f"\n  ⚠ Warning: the following required directives are currently unavailable: {', '.join(missing)}"
        result += "\n  → text-cli;query discoverable via query"

        if not initial_input:
            return result

        # Fall through: register + execute
        result += "\n"

    # 3. Execute path
    mode = path_def.get("mode", "toolchain")
    if mode != "toolchain":
        return f"Unsupported path mode \"{mode}\"（当前仅支持 toolchain）"

    steps = path_def.get("steps", [])
    if not steps:
        return "Path definition has no steps"

    exec_result = _execute_path(path_def, initial_input)

    if register:
        return result + "\n" + exec_result
    return exec_result
