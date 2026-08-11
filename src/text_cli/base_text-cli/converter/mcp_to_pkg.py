"""
mcp_to_pkg.py — 从 MCP server 生成 MCP 桥接包 **模板**。
输出桥接配置骨架，不含完整业务逻辑。

Usage:
    python mcp_to_pkg.py <mcp_server_name> [--out ./my-mcp-pkg/]

Prerequisite:
    The MCP server must already be configured in mcporter.
    Run `mcporter add <server> --transport ...` first.

Workflow:
    mcporter list <server> --json → schema.json + service-descriptor.json 骨架
拿到骨架后请参考 package-dev-guide_zh.md 补全业务逻辑。
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# ── Safe identifiers ────────────────────────────────────

def _safe_id(name: str) -> str:
    return re.sub(r"[^a-z0-9-]", "", name.lower().replace(" ", "-").replace("_", "-"))


def _safe_domain(name: str) -> str:
    """Derive a safe directive domain from the MCP server name."""
    # Strip common prefixes like "server-", "mcp-"
    domain = re.sub(r"^(server-|mcp-|@\w+/)?", "", name.lower())
    domain = _safe_id(domain)
    return domain or "mcp"


def _safe_action(name: str) -> str:
    return _safe_id(name).replace("-", "_")


# ── mcporter interaction ────────────────────────────────

def _list_tools(server: str) -> list[dict]:
    """Run `mcporter list <server> --json` and parse tool list."""
    try:
        result = subprocess.run(
            ["mcporter", "list", server, "--json"],
            capture_output=True, text=True, timeout=30, check=False,
        )
    except FileNotFoundError:
        print("Error: mcporter CLI not found.")
        print("  Install mcporter or configure MCPORTER_BIN in config/mcporter.json")
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print(f"Error: mcporter timed out listing '{server}'.")
        sys.exit(1)

    if result.returncode != 0:
        stderr = result.stderr.strip() or "unknown error"
        print(f"Error: mcporter failed for '{server}': {stderr}")
        print("  Check that the server is configured in mcporter.")
        sys.exit(1)

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        print("Error: mcporter returned invalid JSON.")
        print(f"  Raw output: {result.stdout[:500]}")
        sys.exit(1)

    # mcporter output format: {"tools": [...]} or just [...]
    tools = data.get("tools", data) if isinstance(data, dict) else data
    if not isinstance(tools, list):
        print(f"Error: unexpected mcporter output format for '{server}'.")
        sys.exit(1)

    return tools


# ── Schema generation ───────────────────────────────────

def _build_params(input_schema: dict) -> list[str]:
    """Extract parameter names from MCP tool inputSchema."""
    properties = input_schema.get("properties", {})
    required = set(input_schema.get("required", []))
    # Put required params first
    ordered = sorted(properties.keys(),
                     key=lambda k: (0 if k in required else 1, k))
    return ordered


def _build_params_desc(input_schema: dict) -> dict:
    """Extract parameter descriptions from MCP tool inputSchema."""
    desc = {}
    for name, prop in input_schema.get("properties", {}).items():
        desc[name] = prop.get("description", prop.get("title", ""))
    return desc


def _generate_schema(domain: str, tools: list[dict], server: str) -> str:
    """Generate SPEC-compliant schema.json for MCP bridge package."""
    directives = []
    for tool in tools:
        name = tool.get("name", "")
        description = tool.get("description", "")
        input_schema = tool.get("inputSchema", {})

        action = _safe_action(name)
        params = _build_params(input_schema)
        params_desc = _build_params_desc(input_schema)

        # Required params are shown as <...>; optional params as [...]
        required = set(input_schema.get("required", []))
        usage_parts = [f"<{p}>" if p in required else f"[{p}]" for p in params]

        directives.append({
            "domain": domain,
            "domain_zh": server,
            "action": action,
            "action_zh": name,
            "usage": f"{domain};{action},{','.join(usage_parts)}" if usage_parts else f"{domain};{action}",
            "usage_zh": f"{server};{action},{','.join(usage_parts)}" if usage_parts else f"{server};{action}",
            "description": description or f"MCP tool: {name}",
            "description_zh": description or f"MCP 工具: {name}",
            "params": params,
            "params_desc": params_desc,
            "mcp_tool": name,
        })

    return json.dumps({
        "id": f"tc-mcp-{domain}",
        "name": f"MCP {server} Bridge",
        "name_zh": f"MCP: {server}",
        "version": "0.1.0",
        "description": f"MCP bridge package exposing {len(tools)} tools from '{server}'.",
        "description_zh": f"MCP 桥接包，暴露 '{server}' 的 {len(tools)} 个工具。",
        "runtime": "mcp",
        "type": "native",
        "category": "MCP",
        "locales": ["zh", "en"],
        "trust": "community",
        "mcp_server": server,
        "directives": directives,
    }, ensure_ascii=False, indent=2)


# ── Service descriptor generation ───────────────────────

def _generate_service_descriptor(server: str, tools: list[dict]) -> str:
    """Generate service-descriptor.json for mcporter routing."""
    tool_list = []
    for tool in tools:
        name = tool.get("name", "")
        action = _safe_action(name)
        tool_list.append({
            "name": action,
            "tool": name,
        })

    return json.dumps({
        "mcp_server": server,
        "tools": tool_list,
    }, ensure_ascii=False, indent=2)


# ── Summary ─────────────────────────────────────────────

def _summary(server: str, domain: str, out_dir: str, tools: list[dict],
             schema_bytes: int, sd_bytes: int, entities: list[dict] = None):
    """Print conversion summary with next steps."""
    sample_action = _safe_action(tools[0]["name"]) if tools else "tool"

    print(f"MCP Server : {server}")
    print(f"  Domain     : {domain}")
    print(f"  Tools      : {len(tools)} exported")
    print(f"  Output     : {out_dir}/")
    print(f"    schema.json ({schema_bytes} bytes)")
    print(f"    service-descriptor.json ({sd_bytes} bytes)")
    print()
    print("Review before packaging:")
    print(f"  1. Remove tools you don't want to expose in {out_dir}/schema.json")
    print(f"  2. Improve param descriptions in {out_dir}/schema.json — TODO markers")
    print(f"  3. Verify {out_dir}/service-descriptor.json tool mappings")
    print()
    print("Install and test:")
    print(f"  text-cli;install,{_safe_id(domain)}")
    print(f"  AI:{domain};{sample_action},<params>")


# ── Main ─────────────────────────────────────────────────

def convert(server: str, output_dir: str):
    tools = _list_tools(server)
    if not tools:
        print(f"No tools found for MCP server '{server}'.")
        sys.exit(1)

    domain = _safe_domain(server)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    schema_content = _generate_schema(domain, tools, server)
    (out / "schema.json").write_text(schema_content, encoding="utf-8")

    sd_content = _generate_service_descriptor(server, tools)
    (out / "service-descriptor.json").write_text(sd_content, encoding="utf-8")

    _summary(server, domain, str(out), tools,
             len(schema_content), len(sd_content))


def main():
    parser = argparse.ArgumentParser(
        description="Convert MCP server tools to text-cli MCP bridge package"
    )
    parser.add_argument("server", help="MCP server name (as configured in mcporter)")
    parser.add_argument("--out", "-o", default=None,
                        help="Output directory (default: ./<server-name>/)")
    args = parser.parse_args()

    output_dir = args.out or f"./tc-mcp-{_safe_id(args.server)}/"
    convert(args.server, output_dir)


if __name__ == "__main__":
    main()
