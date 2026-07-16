"""
text-cli MCP Server — 将 text-cli 热指令暴露为 MCP tools

基于 FastMCP，从 text_cli_schema.json 读取指令定义，
每个 tool 内部通过 HTTP POST 调用 text-cli-service (localhost:28050)。

启动后，任何 MCP 客户端（Claude Desktop / Cursor / mcporter）
都可以通过标准 MCP 协议发现和调用 text-cli 指令。

架构：
  MCP 客户端 ←→ FastMCP (port 9020) ←→ text-cli-service (port 28050)

环境变量：
  TEXTCLI_SERVICE_URL  — text-cli-service 地址 (默认 http://localhost:28050/text-cli/cli)
  TEXTCLI_SERVICE_TOKEN — 认证 token (默认 test-token)
  MCP_PORT             — 监听端口 (默认 9020)
"""

import os
import json
import logging

import requests
from fastmcp import FastMCP

# ── 配置 ───────────────────────────────────────────

SERVICE_URL = os.environ.get(
    "TEXTCLI_SERVICE_URL",
    "http://localhost:28050/text-cli/cli"
)
SERVICE_TOKEN = os.environ.get("TEXTCLI_SERVICE_TOKEN", "test-token")
MCP_PORT = int(os.environ.get("MCP_PORT", "9020"))

# ── FastMCP 实例 ────────────────────────────────────

mcp = FastMCP("text-cli")

# ── 内部辅助 ────────────────────────────────────────

logger = logging.getLogger("textcli_mcp")


def _call(directive: str, *params: str) -> str:
    """调用 text-cli-service 并返回 rst_data.text"""
    # 构建 text-cli prompt
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

        # text-cli-service 的 MCP handler 将结果包在 {"content":[...]} JSON 中
        # 尝试展开，取出纯文本内容
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
            # 无法展开则返回原始文本
            return text
        except (json.JSONDecodeError, TypeError):
            return text
    except requests.exceptions.Timeout:
        return "错误: 请求超时 (60s)"
    except requests.exceptions.ConnectionError:
        return f"错误: 无法连接 text-cli-service ({SERVICE_URL})"
    except Exception as e:
        return f"错误: {e}"


# ── 腾讯地图 — 3 tools ──────────────────────────────


@mcp.tool()
def tencentmap_geocode(address: str) -> str:
    """地址解析：将包含省市区的地址转换为经纬度坐标。

    支持结构化地址（如"山东省威海市环翠区"），
    返回纬度、经度、省/市/区 及行政区划代码。
    """
    return _call("tencentmap;geocode", address)


@mcp.tool()
def tencentmap_weather(
    adcode: str = "",
    forecast_type: str = "",
    location: str = ""
) -> str:
    """天气查询：根据行政区划代码或位置查询天气。

    参数至少提供一个：
    - adcode: 行政区划代码，如 371002（威海环翠区）
    - location: 位置名称，如"威海"
    - forecast_type: 预报类型（observe=实况, forecast=预报）
    """
    return _call("tencentmap;weather", adcode, forecast_type, location)


@mcp.tool()
def tencentmap_driving_route(from_addr: str, to_addr: str) -> str:
    """驾车路线规划：从起点到终点的驾车导航路线。

    参数：
    - from_addr: 起点地址，如"威海市政府"
    - to_addr: 终点地址，如"威海火车站"
    返回距离、预估时间和路线步骤。
    """
    return _call("tencentmap;driving_route", from_addr, to_addr)


# ── AntV 蚂蚁图表 — 3 tools ─────────────────────────


@mcp.tool()
def antvchart_pie(config: str) -> str:
    """饼图：生成占比分布的饼图。

    参数 config 为 JSON 字符串，包含图表数据与样式配置。
    返回图表图片 URL。

    示例 config:
    {"data":[{"type":"分类A","value":30},{"type":"分类B","value":70}],"title":"占比分布"}
    """
    return _call("antvchart;pie", config)


@mcp.tool()
def antvchart_line(config: str) -> str:
    """折线图：展示时序变化趋势。

    参数 config 为 JSON 字符串，包含图表数据与样式配置。
    适用于时间序列数据可视化。

    示例 config:
    {"data":[{"date":"2024-01","value":100},{"date":"2024-02","value":150}],"title":"月度趋势"}
    """
    return _call("antvchart;line", config)


@mcp.tool()
def antvchart_scatter(config: str) -> str:
    """散点图：展示变量相关性与数据分布。

    参数 config 为 JSON 字符串，包含图表数据与样式配置。
    适用于回归分析、相关性探索。

    示例 config:
    {"data":[{"x":1,"y":2},{"x":3,"y":5},{"x":5,"y":8}],"title":"相关性分析"}
    """
    return _call("antvchart;scatter", config)


# ── 启动入口 ────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger.info(
        "text-cli MCP Server starting on port %d → %s",
        MCP_PORT, SERVICE_URL
    )
    logger.info("Registered tools: %d", 6)
    mcp.run(transport="sse", host="0.0.0.0", port=MCP_PORT)
