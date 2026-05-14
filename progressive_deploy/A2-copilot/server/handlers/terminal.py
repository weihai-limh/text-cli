"""
Terminal handler — copilot cmd_engine.

Executes whitelisted CLI commands via subprocess.
Each command is validated against its whitelist entry before execution.

This handler is added to copilot as a mixin, not as a replacement
for existing handlers (files, git, mail, etc.).

Author: Tide 🌊 · 2026-05-14
"""

import logging
import subprocess
from pathlib import Path

from core import error, ok

logger = logging.getLogger("copilot.terminal")

# Default whitelist directory (shared with text-cli-service installer)
DEFAULT_WHITELIST_DIR = "/path/to/text-cli/copilot/whitelists"

# Lazy-loaded whitelist index
_whitelist_index = None


def _get_index():
    global _whitelist_index
    if _whitelist_index is None:
        from whitelist_loader import WhitelistIndex
        _whitelist_index = WhitelistIndex(DEFAULT_WHITELIST_DIR)
        logger.info("Whitelist loaded: %s", _whitelist_index)
    return _whitelist_index


class CmdTerminalHandlers:
    """Mixin: CLI command execution via whitelisted subprocess.

    Provides handler methods that are auto-discovered by CopilotCore
    via the naming convention: _handle_<tool>_<action>
    """

    def _handle_openclaw_gateway_status(self, params: list) -> dict:
        """openclaw;gateway-status"""
        return _exec_cmd("openclaw", "gateway-status", params)

    def _handle_openclaw_session_list(self, params: list) -> dict:
        """openclaw;session-list"""
        return _exec_cmd("openclaw", "session-list", params)

    def _handle_openclaw_网关状态(self, params: list) -> dict:
        """openclaw;网关状态 (Chinese alias)"""
        return _exec_cmd("openclaw", "网关状态", params)

    def _handle_openclaw_会话列表(self, params: list) -> dict:
        """openclaw;会话列表 (Chinese alias)"""
        return _exec_cmd("openclaw", "会话列表", params)


def _exec_cmd(tool: str, action: str, params: list) -> dict:
    """Execute a whitelisted CLI command.

    Lookup → validate args → subprocess.run → stdout.
    """
    idx = _get_index()
    entry = idx.lookup(tool, action)

    if entry is None:
        return error("cmd_not_found",
                     f"CLI 指令未在白名单: {tool};{action}")

    # Validate extra params against args_pattern
    extra_args = params  # params passed from text-cli instruction
    pattern = entry.get("_compiled")
    if pattern:
        for p in extra_args:
            if not pattern.match(p):
                return error("cmd_args_denied",
                             f"参数 \"{p}\" 不匹配白名单模式 \"{entry.get('args_pattern', '')}\"")

    # Build command
    cmd = [tool] + entry.get("args", []) + extra_args
    timeout = entry.get("timeout", 30)

    logger.info("cmd exec: %s (timeout=%ds)", " ".join(cmd), timeout)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return error("cmd_timeout",
                     f"命令超时 ({timeout}s): {' '.join(cmd)}")
    except FileNotFoundError:
        return error("cmd_not_found",
                     f"CLI 工具未安装: {tool}")
    except Exception as e:
        return error("cmd_error",
                     f"执行失败: {type(e).__name__}: {e}")

    output = result.stdout.strip()
    if result.returncode != 0:
        stderr_info = result.stderr.strip()
        detail = output or stderr_info or f"exit code {result.returncode}"
        return error("cmd_failed", detail)

    return ok(output or "(无输出)")
