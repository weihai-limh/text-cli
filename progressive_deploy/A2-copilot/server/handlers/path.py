"""
Path handler — copilot-side path execution engine.

Reads a path definition JSON file and executes steps through copilot's
own dispatch. Steps that copilot cannot handle return as delegated,
allowing the caller (Agent or service) to resolve them.

Modes:
  - Execute: AI:text-cli;path,<path_file>[,<input>]
  - Register: AI:text-cli;path,<path_file>,--register  (writes to copilot paths dir)

Author: Tide 🌊 · 2026-05-14
"""

import json
import logging
import pathlib
import re
from typing import Any

from core import error, ok

logger = logging.getLogger("copilot.path")

VAR_RE = re.compile(r'\$\{(\w+)\}')

# Copilot's own paths directory (separate from service)
COPILOT_PATHS_DIR = pathlib.Path("/path/to/text-cli/copilot/paths")

# Required fields for path registration
_REQUIRED_DECLARATION = frozenset({"id", "name", "version", "type", "steps"})


def _resolve_var(text: str, variables: dict[str, str]) -> str:
    def _repl(m):
        return variables.get(m.group(1), m.group(0))
    return VAR_RE.sub(_repl, text)


def _parse_directive(raw: str) -> tuple[str, str, list[str]]:
    """Parse 'domain;action,param1,param2'."""
    d = raw.strip()
    if ':' in d and not d.startswith('AI:'):
        pass
    elif d.startswith('AI:'):
        d = d[3:]

    if ',' in d:
        parts = d.split(',', 1)
        head = parts[0]
        params = [p.strip() for p in parts[1:]]
    else:
        head = d
        params = []

    if ';' in head:
        domain, action = head.split(';', 1)
    else:
        domain = head
        action = ""

    return domain.strip(), action.strip(), params


class PathHandlers:
    """Mixin: path execution for copilot.

    Provides text-cli;path handler that executes path definitions
    through copilot's dispatch system.
    """

    def _handle_text_cli_path(self, params: list) -> dict:
        """Execute or register a path definition."""
        return self._execute_path_cmd(params)

    def _handle_文本指令_路径(self, params: list) -> dict:
        """Chinese alias."""
        return self._execute_path_cmd(params)

    def _execute_path_cmd(self, params: list) -> dict:
        """Core path execution logic."""
        if not params:
            return ok(
                "用法:\n"
                "  AI:text-cli;path,<路径文件>[,<初始输入>]          → 执行\n"
                "  AI:text-cli;path,<路径文件>,--register           → 注册\n\n"
                "copilot 路径引擎：在 copilot 本地 dispatch 上下文中执行步骤。\n"
                "不认识的指令返回 delegated 而非报错。"
            )

        path_file = params[0].strip()
        register = False
        initial_input = ""

        for p in params[1:]:
            ps = p.strip()
            if ps == "--register":
                register = True
            else:
                initial_input = ps

        # Load
        p = pathlib.Path(path_file)
        if not p.is_file():
            return error("path_not_found", f"路径文件不存在: {path_file}")

        try:
            path_def = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            return error("path_parse_error", f"路径文件解析失败: {e}")

        # --register mode
        if register:
            return self._register_copilot_path(path_def, path_file)

        # Execute
        return self._execute_steps(path_def, initial_input)

    def _register_copilot_path(self, path_def: dict, source_file: str) -> dict:
        """Register a path declaration in copilot's paths directory."""
        missing = [f for f in _REQUIRED_DECLARATION if f not in path_def]
        if missing:
            return error("path_invalid", f"缺少必填字段: {', '.join(missing)}")

        path_id = path_def["id"]
        output = {
            "id": path_id,
            "name": path_def.get("name_en", path_def.get("name", path_id)),
            "name_cn": path_def.get("name", path_id),
            "version": path_def.get("version", "0.1.0"),
            "type": path_def.get("type", "skill"),
            "mode": path_def.get("mode", "toolchain"),
            "description": path_def.get("description", ""),
            "description_cn": path_def.get("description_cn", ""),
            "input_schema": path_def.get("input_schema", {}),
            "output_schema": path_def.get("output_schema", {}),
            "requires": path_def.get("requires", []),
            "steps": path_def.get("steps", []),
            "source_file": source_file,
        }

        COPILOT_PATHS_DIR.mkdir(parents=True, exist_ok=True)
        out_path = COPILOT_PATHS_DIR / f"path_{path_id}.json"
        try:
            out_path.write_text(
                json.dumps(output, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError as e:
            return error("path_write_error", f"写入失败: {e}")

        logger.info("Path registered on copilot: %s → %s", path_id, out_path)
        return ok(
            f"路径已注册: {path_def.get('name', path_id)} (v{path_def.get('version', '?')})\n"
            f"  id: {path_id}\n"
            f"  注册位置: {out_path}\n"
            f"  → copilot 侧可见"
        )

    def _execute_steps(self, path_def: dict, initial_input: str) -> dict:
        """Execute path steps through copilot dispatch. Unknown steps → delegated."""
        steps = path_def.get("steps", [])
        if not steps:
            return error("path_empty", "路径定义中没有步骤")

        path_name = path_def.get("name", path_def.get("id", "unnamed"))
        variables: dict[str, str] = {"input": initial_input}
        delegated: list[dict] = []
        completed: list[dict] = []
        log_lines = [f"═══ {path_name} ═══"]

        for i, step in enumerate(steps, 1):
            raw = step.get("directive", "")
            if not raw:
                return error("path_step_error", f"[步骤 {i}] 缺少 directive")

            resolved = _resolve_var(raw, variables)
            domain, action, params = _parse_directive(resolved)

            if not domain:
                return error("path_step_error", f"[步骤 {i}] 无法解析: {resolved}")

            # Try copilot dispatch
            try:
                result = self.dispatch({
                    "domain": domain,
                    "action": action,
                    "params": params,
                })
            except Exception as e:
                log_lines.append(f"  [{i}] {raw} ✗ {e}")
                return error("path_step_error", f"[步骤 {i}] 执行异常: {e}")

            output_as = step.get("output_as", f"_step{i}")

            # Check if copilot handled it
            if result.get("rst_err") == "unknown_instruction":
                delegated.append({
                    "step": i,
                    "directive": f"{domain};{action}",
                    "output_as": output_as,
                })
                log_lines.append(f"  [{i}] {raw} ⤴ delegated")
                continue

            if "rst_err" in result:
                log_lines.append(f"  [{i}] {raw} ✗ {result.get('rst_err')}")
                return result  # Propagate error

            output_text = result.get("rst_data", {}).get("text", "")
            variables[output_as] = output_text
            short = output_text[:80] + ("…" if len(output_text) > 80 else "")
            completed.append({"step": i, "directive": raw, "output_as": output_as})
            log_lines.append(f"  [{i}] {raw} ✓ ({output_as})")
            if short:
                log_lines.append(f"      → {short}")

        # Build result
        if delegated:
            log_lines.append("")
            log_lines.append(f"[部分完成] {len(completed)}/{len(steps)} 步骤完成")
            log_lines.append(f"[需上层处理] {json.dumps(delegated, ensure_ascii=False)}")
            return ok(
                "\n".join(log_lines),
                completed=len(completed),
                total=len(steps),
                delegated=delegated,
            )

        final = variables.get(f"_step{len(steps)}", "")
        if not final:
            for step in reversed(steps):
                key = step.get("output_as", "")
                if key in variables:
                    final = variables[key]
                    break

        log_lines.append(f"\n[完成]\n{final}" if final.strip() else "\n[完成]")
        return ok("\n".join(log_lines))
