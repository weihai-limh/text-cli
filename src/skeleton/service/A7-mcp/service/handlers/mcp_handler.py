"""
MCP call handler — invoke MCP tools via mcporter.

Infrastructure resolution (3-layer fallback):
  1. service/config/mcporter.json  — explicit user config
  2. text_cli_modules/bin/mcporter — zero-config auto-discovery
  3. PATH                          — system / Docker install (fallback)

Isomorphic with copilot's mcp_handler — same mcporter subprocess pattern.
"""

import json
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

# ── mcporter infrastructure resolution ─────────────

_MODULES_ROOT = Path(__file__).resolve().parent.parent.parent / "text_cli_modules"
_SERVICE_CONFIG = Path(__file__).resolve().parent.parent / "config"

_MCPORTER_CONFIG_PATH = _SERVICE_CONFIG / "mcporter.json"

_MCPORTER_HELP = (
    "MCP call engine not ready: mcporter not found.\n\n"
    "Available options:\n"
    "  a) Create service/config/mcporter.json with bin and cwd\n"
    "  b) Place mcporter binary at text_cli_modules/bin/mcporter\n"
    "  c) Install mcporter globally (available on PATH)\n\n"
    "Search order: config/mcporter.json -> text_cli_modules/bin/mcporter -> PATH"
)


def _resolve_mcporter():
    """Resolve mcporter binary + working directory via 3-layer fallback.

    Returns:
        (bin_path: str, cwd: str | None)
    Raises:
        FileNotFoundError: mcporter not found at any layer (with _MCPORTER_HELP message)
    """
    # Layer 1: explicit config
    if _MCPORTER_CONFIG_PATH.exists():
        try:
            cfg = json.loads(_MCPORTER_CONFIG_PATH.read_text(encoding="utf-8"))
            bin_path = cfg.get("bin", "mcporter")
            cwd = cfg.get("cwd")
            if Path(bin_path).exists() or bin_path == "mcporter":
                logger.debug("mcporter resolved via config: bin=%s cwd=%s", bin_path, cwd)
                return bin_path, cwd
            raise FileNotFoundError(f"mcporter binary not found at configured path: {bin_path}")
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("Invalid mcporter.json: %s, falling through", e)

    # Layer 2: auto-discovery in text_cli_modules/bin/
    auto_bin = _MODULES_ROOT / "bin" / "mcporter"
    if auto_bin.exists():
        auto_cwd = _MODULES_ROOT / "bin"
        logger.debug("mcporter resolved via auto-discovery: %s", auto_bin)
        return str(auto_bin), str(auto_cwd)

    # Layer 3: PATH fallback
    try:
        result = subprocess.run(
            ["mcporter", "--version"],
            capture_output=True, text=True, timeout=5, check=False,
        )
        if result.returncode == 0:
            logger.debug("mcporter resolved via PATH")
            return "mcporter", None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    raise FileNotFoundError(_MCPORTER_HELP)


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
        mcporter_bin, mcporter_cwd = _resolve_mcporter()
    except FileNotFoundError as e:
        return {"ok": False, "degrade": True, "error": str(e)}

    try:
        result = subprocess.run(
            [mcporter_bin, 'call', server, tool,
             '--args', args_json, '--output', 'json', '--raw-strings'],
            capture_output=True, text=True,
            timeout=timeout_sec,
            cwd=mcporter_cwd or None, check=False,
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
