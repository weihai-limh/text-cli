"""
text-cli MCP Server — Expose text-cli hot directives as MCP tools

Built on FastMCP. Reads directive definitions from text_cli_schema.json,
exposes each as an MCP tool. Tools call text-cli-service via HTTP POST.

Architecture:
  MCP Client ←→ FastMCP (this server) ←→ text-cli-service

This turns text-cli from an MCP consumer into an MCP provider,
completing the bidirectional bridge.

Environment variables:
  TEXTCLI_SERVICE_URL   — text-cli-service endpoint (default http://localhost:28050/cli/text_cli)
  TEXTCLI_SERVICE_TOKEN — auth token (default test-token)
  MCP_PORT              — listen port (default 9020)
  TEXTCLI_SCHEMA_PATH   — path to schema JSON (default ../config/text_cli_schema.json)

Requirements:
  pip install fastmcp requests
"""

import os
import json
import logging

import requests
from fastmcp import FastMCP

# ── Configuration ────────────────────────────────────

SERVICE_URL = os.environ.get(
    "TEXTCLI_SERVICE_URL",
    "http://localhost:28050/cli/text_cli"
)
SERVICE_TOKEN = os.environ.get("TEXTCLI_SERVICE_TOKEN", "test-token")
MCP_PORT = int(os.environ.get("MCP_PORT", "9020"))
SCHEMA_PATH = os.environ.get(
    "TEXTCLI_SCHEMA_PATH",
    os.path.join(os.path.dirname(__file__), "..", "config", "text_cli_schema.json")
)

# ── FastMCP instance ─────────────────────────────────

mcp = FastMCP("text-cli")

# ── Internal helpers ─────────────────────────────────

logger = logging.getLogger("textcli_mcp")


def _call(directive: str, *params: str) -> str:
    """Call text-cli-service and return rst_data.text"""
    parts = [directive]
    parts.extend(str(p) for p in params if p)
    prompt = "AI:" + ",".join(parts)

    try:
        resp = requests.post(
            SERVICE_URL,
            json={"prompt": prompt},
            headers={"Service-token": SERVICE_TOKEN},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        text = data.get("rst_data", {}).get("text", "")
        if not text:
            return json.dumps(data, ensure_ascii=False)

        # text-cli-service MCP handler wraps results in {"content":[...]} JSON.
        # Attempt to unwrap and extract plain text content.
        try:
            inner = json.loads(text)
            content_list = inner.get("content", [])
            if content_list:
                texts = []
                for item in content_list:
                    if item.get("type") == "text":
                        texts.append(item.get("text", ""))
                if texts:
                    return "\n".join(texts)
            return text
        except (json.JSONDecodeError, TypeError):
            return text
    except requests.exceptions.Timeout:
        return "Error: request timeout (60s)"
    except requests.exceptions.ConnectionError:
        return f"Error: cannot connect to text-cli-service ({SERVICE_URL})"
    except Exception as e:
        return f"Error: {e}"


# ── Tool registration ────────────────────────────────
# Each tool wraps one text-cli directive.
# Add or remove tools below to match your schema's hot directives.


@mcp.tool()
def tencentmap_geocode(address: str) -> str:
    """Geocode: convert a structured address to lat/lng coordinates.

    Supports addresses containing province/city/district (e.g. "山东省威海市环翠区").
    Returns latitude, longitude, province/city/district and administrative division code.
    """
    return _call("tencentmap;geocode", address)


@mcp.tool()
def tencentmap_weather(
    adcode: str = "",
    forecast_type: str = "",
    location: str = ""
) -> str:
    """Weather query: get weather by administrative division code or location name.

    Provide at least one of:
    - adcode: administrative division code, e.g. 371002
    - location: location name, e.g. "威海"
    - forecast_type: "observe" for current, "forecast" for prediction
    """
    return _call("tencentmap;weather", adcode, forecast_type, location)


@mcp.tool()
def tencentmap_driving_route(from_addr: str, to_addr: str) -> str:
    """Driving route: plan a driving route from origin to destination.

    Args:
    - from_addr: origin address, e.g. "威海市政府"
    - to_addr: destination address, e.g. "威海火车站"
    Returns distance, estimated time, and route steps.
    """
    return _call("tencentmap;driving_route", from_addr, to_addr)


@mcp.tool()
def antvchart_pie(config: str) -> str:
    """Pie chart: generate a pie chart showing proportional distribution.

    config is a JSON string with chart data and style configuration.
    Returns a chart image URL.

    Example config:
    {"data":[{"type":"Category A","value":30},{"type":"Category B","value":70}],"title":"Distribution"}
    """
    return _call("antvchart;pie", config)


@mcp.tool()
def antvchart_line(config: str) -> str:
    """Line chart: display trend over time.

    config is a JSON string with chart data and style configuration.
    Suitable for time-series visualization.

    Example config:
    {"data":[{"date":"2024-01","value":100},{"date":"2024-02","value":150}],"title":"Monthly Trend"}
    """
    return _call("antvchart;line", config)


@mcp.tool()
def antvchart_scatter(config: str) -> str:
    """Scatter plot: show correlation and data distribution.

    config is a JSON string with chart data and style configuration.
    Suitable for regression analysis and correlation exploration.

    Example config:
    {"data":[{"x":1,"y":2},{"x":3,"y":5},{"x":5,"y":8}],"title":"Correlation Analysis"}
    """
    return _call("antvchart;scatter", config)


# ── Entry point ──────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger.info(
        "text-cli MCP Server starting on port %d → %s",
        MCP_PORT, SERVICE_URL
    )
    logger.info("Registered tools: %d", 6)
    mcp.run(transport="sse", host="0.0.0.0", port=MCP_PORT)
