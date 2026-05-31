# text-cli MCP Bridge

Expose text-cli directives as MCP tools via FastMCP.

This server reads directive definitions from `text_cli_schema.json` and exposes each hot directive as an MCP tool. Any MCP client (Claude Desktop, Cursor, mcporter) can discover and invoke text-cli directives through the standard MCP protocol.

Completes the bidirectional bridge: text-cli is both an MCP **consumer** (via mcp2textcli) and an MCP **provider** (via this server).

## Architecture

```
MCP Client ←→ FastMCP (:9020) ←→ text-cli-service (:28050)
```

## Quick Start

```bash
# 1. Install dependencies
pip install fastmcp requests

# 2. Start
./manage.sh start

# 3. Verify
./manage.sh status
# → MCP server running (pid 12345, port 9020)
# → SSE: http://localhost:9020/sse
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `TEXTCLI_SERVICE_URL` | `http://localhost:28050/cli/text_cli` | text-cli-service endpoint |
| `TEXTCLI_SERVICE_TOKEN` | `test-token` | Auth token |
| `MCP_PORT` | `9020` | Listen port |
| `TEXTCLI_SCHEMA_PATH` | `../config/text_cli_schema.json` | Schema path |

## Management

```bash
./manage.sh start     # Start server
./manage.sh stop      # Stop server
./manage.sh restart   # Restart server
./manage.sh status    # Check status
./manage.sh logs      # View recent logs
```

## Adding Tools

Edit `server.py` and add a new `@mcp.tool()` function for each directive you want to expose. Each tool wraps one `_call("domain;action", params...)`.

Example:

```python
@mcp.tool()
def my_service_query(param: str) -> str:
    """Query description for MCP clients."""
    return _call("myservice;query", param)
```
