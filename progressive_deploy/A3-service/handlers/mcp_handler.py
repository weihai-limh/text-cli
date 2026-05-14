"""
MCP call handler — invoke MCP tools via mcporter.

Isomorphic with copilot's mcp_handler — same mcporter subprocess pattern.
"""

import json
import logging
import subprocess

logger = logging.getLogger(__name__)

# mcporter working directory (where config lives)
MCWD = "/root/.openclaw/workspace"


def call_mcp_tool(server: str, tool: str, arguments: dict,
                  timeout_ms: int = 30000) -> dict:
    """
    Invoke an MCP tool.

    Args:
        server: MCP server name (key in mcporter config)
        tool: MCP tool name
        arguments: parameter dict
        timeout_ms: timeout in milliseconds

    Returns:
        {"ok": True, "result": <parsed JSON>}
        or {"ok": False, "error": <message>}
    """
    timeout_sec = max(1, timeout_ms // 1000)
    args_json = json.dumps(arguments)

    logger.info("MCP call: %s.%s args=%s", server, tool, args_json[:200])

    try:
        result = subprocess.run(
            ['mcporter', 'call', server, tool,
             '--args', args_json, '--output', 'json', '--raw-strings'],
            capture_output=True, text=True,
            timeout=timeout_sec,
            cwd=MCWD,
        )

        if result.returncode == 0:
            parsed = json.loads(result.stdout)
            # mcporter may return errors in stdout JSON with exit code 0
            if isinstance(parsed, dict) and "error" in parsed:
                return {"ok": False, "error": parsed.get("error", "unknown"),
                        "detail": parsed.get("issue", {})}
            return {"ok": True, "result": parsed}
        else:
            err = result.stderr or result.stdout
            return {"ok": False, "error": err.strip()}

    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "MCP timeout"}
    except json.JSONDecodeError:
        return {"ok": False, "error": f"MCP invalid JSON: {result.stdout[:200]}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def format_mcp_result(mcp_result: dict) -> str:
    """Format MCP call result as text-cli response text."""
    if not mcp_result["ok"]:
        return json.dumps({
            "server": "mcp",
            "error": mcp_result["error"],
        }, ensure_ascii=False)

    data = mcp_result["result"]

    # Smart formatting for common MCP return structures
    if isinstance(data, dict):
        # GitHub API style
        if "total_count" in data:
            items = data.get("items", [])
            total = data["total_count"]
            return json.dumps({
                "total": total,
                "count": len(items),
                "sample": [
                    item.get("full_name") or item.get("path") or item.get("name") or item.get("html_url") or str(item)[:80]
                    for item in items[:5]
                ]
            }, ensure_ascii=False)
        # Single object patterns
        if "sha" in data:
            return json.dumps({"sha": data["sha"][:12]}, ensure_ascii=False)
        if "number" in data and "title" in data:
            return json.dumps({"number": data["number"], "title": data["title"]}, ensure_ascii=False)
        if "html_url" in data:
            return json.dumps({"url": data["html_url"], "id": data.get("id", "")}, ensure_ascii=False)

    return json.dumps(data, ensure_ascii=False)
