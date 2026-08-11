"""
MCP tool caller — bridge text-cli directives to MCP tools via mcporter CLI.

This is a reference implementation using the ``mcporter`` CLI as the MCP transport.
The interface pattern (call → parse → text-cli response) is universal;
the implementation (subprocess → mcporter) is one choice among many.

Alternatives:
  - Python MCP SDK (mcp.ClientSession) for direct stdio/SSE connections
  - HTTP gateway for remote MCP servers behind a firewall
  - In-process plugin for MCP servers with Python bindings

Directives routed through this handler end up as:
  text-cli params → adapt_params → MCP tool arguments → mcporter call → parse → response

Dependencies:
  - mcporter CLI (npm install -g mcporter or pip install mcporter)
  - mcporter config at ~/.openclaw/workspace/config/mcporter.json (or MCPORTER_CONFIG env)

Usage:
  from mcp_handler import call_mcp_tool, parse_mcp_result

  ok, text = call_mcp_tool('tencent-maps', 'tencentmap_geocode', {'address': '威海'})
  if ok:
      response = parse_mcp_result(text)
"""

import json
import os
import subprocess
import time


def call_mcp_tool(
    server: str,
    tool: str,
    arguments: dict,
    timeout_ms: int = 30000,
    workspace_dir: str = None,
) -> tuple[bool, str]:
    """Call an MCP tool via mcporter CLI.

    Args:
        server:      MCP server name (as configured in mcporter)
        tool:        tool name to invoke
        arguments:   tool arguments as a dict
        timeout_ms:  subprocess timeout in milliseconds
        workspace_dir: working directory for mcporter (default: MCPORTER_WORKSPACE env or cwd)

    Returns:
        (success: bool, result_text: str)
    """
    if workspace_dir is None:
        workspace_dir = os.environ.get('MCPORTER_WORKSPACE', os.getcwd())

    try:
        args_json = json.dumps(arguments)
        start = time.monotonic()

        result = subprocess.run(
            [
                'mcporter', 'call', server, tool,
                '--args', args_json,
                '--output', 'json',
                '--raw-strings',
            ],
            capture_output=True,
            text=True,
            timeout=timeout_ms / 1000,
            cwd=workspace_dir,
            check=False,
        )

        elapsed = time.monotonic() - start
        print(f"[mcp_handler] {server}.{tool} → {elapsed:.2f}s")

        if result.returncode != 0:
            err = result.stderr.strip() or result.stdout.strip()
            return False, f'mcporter call failed (exit={result.returncode}): {err}'

        return True, result.stdout.strip()

    except subprocess.TimeoutExpired:
        return False, f'MCP tool call timed out ({timeout_ms}ms)'
    except FileNotFoundError:
        return False, 'mcporter CLI not installed or not in PATH'
    except Exception as e:
        return False, f'MCP call exception: {type(e).__name__}: {e}'


def parse_mcp_result(raw: str) -> dict:
    """Parse mcporter output into a standard text-cli response dict.

    If the result is already in text-cli format (has ``rst_types``), pass through.
    If it's valid JSON, wrap it as formatted text.
    Otherwise treat it as plain text.

    Args:
        raw: raw stdout from mcporter call

    Returns:
        {'rst_types': str, 'rst_data': {...}} ready for direct return
    """
    if not raw or not raw.strip():
        return {
            'rst_types': 'text',
            'rst_data': {'text': '(MCP tool returned empty result)'},
        }

    # Try JSON — some MCP tools return structured data
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            # Already text-cli format? Pass through.
            if 'rst_types' in parsed:
                return parsed
            # Otherwise wrap as formatted text
            return {
                'rst_types': 'text',
                'rst_data': {
                    'text': json.dumps(parsed, ensure_ascii=False, indent=2)
                },
            }
    except json.JSONDecodeError:
        pass

    return {
        'rst_types': 'text',
        'rst_data': {'text': raw},
    }
