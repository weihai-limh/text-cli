# with-mcporter — MCP Consumer via mcporter CLI

Reference implementation for calling MCP tools from within a text-cli copilot.

**This directory requires `mcporter` — it is NOT zero-dependency like `base/`.**

## What it does

`mcp_handler.py` bridges text-cli directives to MCP tools:

```
text-cli params → adapt to MCP args → mcporter call → parse → text-cli response
```

Two functions:

| Function | Role |
|---|---|
| `call_mcp_tool(server, tool, arguments)` | Invoke MCP tool via subprocess |
| `parse_mcp_result(raw_text)` | Convert mcporter output to text-cli format |

## Dependencies

```bash
# mcporter CLI (choose one)
npm install -g mcporter
# or: pip install mcporter

# mcporter config expected at:
# ~/.openclaw/workspace/config/mcporter.json
```

## Usage

```python
from mcp_handler import call_mcp_tool, parse_mcp_result

ok, raw = call_mcp_tool('tencent-maps', 'tencentmap_geocode', {'address': '威海'})
if ok:
    response = parse_mcp_result(raw)
    # response → {'rst_types': 'text', 'rst_data': {...}}
```

## Alternatives

This implementation uses `mcporter` subprocess. The same interface pattern works with:

- **Python MCP SDK** — `mcp.ClientSession` for direct stdio/SSE, no subprocess
- **HTTP gateway** — POST to a remote MCP bridge, suitable for firewalled servers
- **In-process plugin** — import MCP server as a Python module if it exposes Python bindings

The interface (`call → parse → response`) is what matters. The transport is replaceable.
