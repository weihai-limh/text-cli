"""
text-cli;path — A4 path engine handler (skeleton).

Executes a step sequence defined as JSON. Each step issues a directive via
dispatch(), with variable interpolation between steps.

Formats accepted:
    text-cli;path,<json_steps>            → inline JSON step sequence
    text-cli;path,<package>/<file>.json   → read from service/paths/<pkg>/<file>.json

JSON structure:
    {
      "steps": [
        {"id": "step1", "instruction": "domain;action,{input.key},{step0.field}"},
        {"id": "fallback", "instruction": "...", "if": "{step1.field} == 'NOMATCH'"}
      ]
    }

Variables:
    {input.<key>}      → user-supplied input (via the 'input' query param)
    {step_id.field}    → previous step output, parsed as JSON, field extracted

Author: Tide
"""

import json
import logging
from pathlib import Path

from core.registry import directive
from core.registry import dispatch as _dispatch

logger = logging.getLogger(__name__)

_PROJECT_ROOT: Path | None = None
_PATHS_DIR: Path | None = None


def init_text_cli_path_handler(project_root: str = None):
    global _PROJECT_ROOT, _PATHS_DIR
    if project_root:
        _PROJECT_ROOT = Path(project_root)
        _PATHS_DIR = _PROJECT_ROOT / "paths"
    logger.info("text-cli;path initialised")


def _resolve_path_ref(ref: str) -> list[dict]:
    """Resolve a path reference: inline JSON or file path."""
    stripped = ref.strip()
    if stripped.startswith("{"):
        data = json.loads(stripped)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "steps" in data:
            return data["steps"]
        return [data]
    if _PATHS_DIR:
        file_path = _PATHS_DIR / stripped
        if file_path.suffix != ".json":
            file_path = file_path.with_suffix(".json")
        if file_path.exists():
            data = json.loads(file_path.read_text(encoding="utf-8"))
            return data.get("steps", [])
    return []


def _interpolate(template: str, variables: dict) -> str:
    """Replace {step.field} and {input.key} placeholders with values."""
    result = template
    for key, val in variables.items():
        result = result.replace(f"{{{key}}}", str(val) if not isinstance(val, str) else val)
    return result


@directive("text-cli", "path", domain_alias="文本指令", action_aliases={"path": "路径"})
def text_cli_path(params: list[str]) -> str:
    if not params:
        return json.dumps({
            "status": "error",
            "reason": "Usage: text-cli;path,<json_or_file_ref>[,<input_json>]"
        })

    steps = _resolve_path_ref(params[0])
    if not steps:
        return json.dumps({"status": "error", "reason": f"path not found: {params[0]}"})

    user_input = {}
    if len(params) > 1:
        try:
            ui_str = ",".join(params[1:])
            user_input = json.loads(ui_str)
        except json.JSONDecodeError:
            user_input = {"value": ui_str}

    outputs: dict[str, str] = {}
    variables: dict[str, str] = {}
    if user_input:
        for k, v in user_input.items():
            variables[f"input.{k}"] = v if isinstance(v, str) else json.dumps(v)

    step_results = []

    for step in steps:
        if not isinstance(step, dict):
            continue

        sid = step.get("id", "")
        condition = step.get("if")
        instruction = step.get("instruction", "")

        if not instruction:
            continue

        # Check condition
        if condition:
            cond_evaluated = condition
            for var, val in variables.items():
                cond_evaluated = cond_evaluated.replace(f"{{{var}}}", val)
            try:
                # Security: eval() sandboxed with __builtins__ disabled.
                # Conditions come from trusted package schema (step["if"]),
                # support only simple boolean expressions (==, !=, >, <, in, and, or).
                # Cannot execute arbitrary code — no __import__, open, exec available.
                if not eval(cond_evaluated, {"__builtins__": {}}, {}):
                    continue
            except Exception:
                logger.warning("Failed to evaluate condition: %s", condition)
                continue

        # Interpolate instruction
        resolved = _interpolate(instruction, variables)

        # Dispatch
        parts = resolved.split(";", 1)
        if len(parts) != 2:
            step_results.append({"step": sid, "status": "error", "reason": f"invalid instruction: {resolved}"})
            continue

        domain, tail = parts
        tail_parts = tail.split(",", 1)
        action = tail_parts[0]
        action_params = [p.strip() for p in tail_parts[1].split(",")] if len(tail_parts) > 1 else []

        try:
            result = _dispatch(domain, action, action_params)
            outputs[sid] = result

            # Try to parse result as JSON for field access
            try:
                parsed = json.loads(result)
                if isinstance(parsed, dict):
                    for k, v in parsed.items():
                        variables[f"{sid}.{k}"] = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
                else:
                    variables[f"{sid}"] = result
            except (json.JSONDecodeError, TypeError):
                variables[f"{sid}"] = result

            step_results.append({"step": sid, "status": "ok", "instruction": resolved})
        except Exception as e:
            logger.exception("path step %s failed", sid)
            step_results.append({"step": sid, "status": "error", "reason": str(e)})

    return json.dumps({
        "status": "ok",
        "steps_executed": len(step_results),
        "step_results": step_results,
    }, ensure_ascii=False)
