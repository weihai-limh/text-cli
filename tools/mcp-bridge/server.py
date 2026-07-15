"""
text-cli MCP Server — 配置驱动的 text-cli → MCP 协议桥

从 mcp_exposure.json 读取暴露清单，自动从 text-cli-service 的
指令 schema 中获取定义，动态生成 MCP 工具函数并注册。

启动后，任何 MCP 客户端（Claude Desktop / Cursor / mcporter）
都可以通过标准 MCP 协议发现和调用 text-cli 指令。

架构：
  MCP 客户端 ←→ FastMCP (port 9020) ←→ text-cli-service (port 28050)

环境变量：
  TEXTCLI_SERVICE_URL  — text-cli-service 地址 (默认 http://localhost:28050/cli/text_cli)
  TEXTCLI_SERVICE_TOKEN — 认证 token (默认 your-service-token-here)
  MCP_PORT             — 监听端口 (默认 9020)

配置：
  mcp_exposure.json — 暴露清单（domain;action 数组），和 server.py 同目录

Author: Tide 🌊 · 2026-05-14 · v2 配置驱动重写
"""

import json
import logging
import os
import pathlib
import re
from typing import Optional

import requests
from fastmcp import FastMCP

# ── 环境变量 ──────────────────────────────────────

SERVICE_URL = os.environ.get(
    "TEXTCLI_SERVICE_URL",
    "http://localhost:28050/cli/text_cli",
)
SERVICE_TOKEN = os.environ.get("TEXTCLI_SERVICE_TOKEN", "your-service-token-here")
MCP_PORT = int(os.environ.get("MCP_PORT", "9020"))

# ── 路径 ──────────────────────────────────────────

HERE = pathlib.Path(__file__).parent
EXPOSURE_PATH = pathlib.Path(os.environ.get("TEXTCLI_EXPOSURE_PATH", str(HERE / "mcp_exposure.json")))
SCHEMA_DIR = pathlib.Path(os.environ.get(
    "TEXTCLI_SCHEMA_DIR",
    str(pathlib.Path(__file__).parent.parent.parent / "service" / "handlers" / "schema")
))

# ── FastMCP 实例 ──────────────────────────────────

mcp = FastMCP("text-cli")
logger = logging.getLogger("textcli_mcp")


# ── text-cli 调用 ─────────────────────────────────

def _call_textcli(directive: str, *params: str) -> str:
    """调用 text-cli-service 并返回 rst_data.text 或格式化结果。"""
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

        # 尝试展开 MCP handler 的 {"content":[...]} 包装
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
        return "错误: 请求超时 (60s)"
    except requests.exceptions.ConnectionError:
        return f"错误: 无法连接 text-cli-service ({SERVICE_URL})"
    except Exception as e:
        return f"错误: {e}"


# ── 配置加载 ──────────────────────────────────────

def _load_exposure() -> list[str]:
    """加载暴露清单（domain;action 数组）。"""
    try:
        with open(EXPOSURE_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        return cfg.get("expose", [])
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning("无法加载 mcp_exposure.json: %s", e)
        return []


def _load_schema_map() -> dict[str, dict]:
    """加载 service 的指令 schema，构建 {domain;action: directive_def} 映射。

    读取 handlers/schema/*.json，提取 directives 数组中的每一条，
    同时注册中英文变体到同一映射。
    """
    schema_map: dict[str, dict] = {}

    if not SCHEMA_DIR.exists():
        logger.warning("Schema 目录不存在: %s", SCHEMA_DIR)
        return schema_map

    for sf in sorted(SCHEMA_DIR.glob("*_schema.json")):
        try:
            schema = json.loads(sf.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        for d in schema.get("directives", []):
            domain = d.get("domain", "")
            action = d.get("action", "")
            if not domain or not action:
                continue

            key = f"{domain};{action}"
            schema_map[key] = d

            # 中文变体
            dc = d.get("domain_cn", "")
            ac = d.get("action_cn", "")
            if dc and ac and f"{dc};{ac}" != key:
                schema_map[f"{dc};{ac}"] = d

    return schema_map


# ── 参数名提取 ────────────────────────────────────

_PARAM_NAME_RE = re.compile(r"<(\w+)>")
_PARAM_SANITIZE_RE = re.compile(r"[^\w]")

# Python keywords that can't be parameter names
_PYTHON_KEYWORDS = frozenset({
    "from", "import", "class", "def", "if", "else", "elif",
    "for", "while", "try", "except", "finally", "with", "as",
    "return", "yield", "lambda", "and", "or", "not", "in", "is",
    "True", "False", "None", "pass", "break", "continue", "raise",
    "global", "nonlocal", "assert", "del", "async", "await",
    "type",  # builtin that can cause issues in some contexts
})


def _extract_param_names(directive_def: dict) -> list[str]:
    """从指令定义中提取 MCP 工具参数名。

    优先从 usage 字符串的 <param> 尖括号中提取，
    回退到使用 param_N 命名。
    Python 关键字自动加 _ 前缀。
    """
    usage = directive_def.get("usage", "")
    names = _PARAM_NAME_RE.findall(usage)
    if names:
        # Sanitize: replace Python keywords and non-alphanumeric chars
        sanitized = []
        for n in names:
            n = _PARAM_SANITIZE_RE.sub("_", n)
            if n in _PYTHON_KEYWORDS:
                n = f"{n}_"
            sanitized.append(n)
        return sanitized

    # 回退：从 params 数组中推断
    params = directive_def.get("params", [])
    return [f"param_{i + 1}" for i in range(len(params))]


# ── 动态工具注册 ──────────────────────────────────

def _register_tools():
    """从暴露配置和 schema 动态注册 MCP 工具。

    使用 exec() 动态生成带显式参数签名的工具函数，
    因为 FastMCP 不支持 **kwargs。
    """
    exposure = _load_exposure()
    schema_map = _load_schema_map()

    registered = 0
    skipped = []
    tool_ns = {"_call_textcli": _call_textcli}

    for directive_id in exposure:
        directive_def = schema_map.get(directive_id)
        if directive_def is None:
            skipped.append(directive_id)
            logger.warning("MCP expose: 指令未在 schema 中找到 — %s", directive_id)
            continue

        param_names = _extract_param_names(directive_def)
        domain = directive_def.get("domain", "")
        action = directive_def.get("action", "")
        description = directive_def.get("description_cn", directive_def.get("description", ""))

        # 生成工具名和函数名
        tool_name = f"{domain}_{action}".replace("-", "_").replace(".", "_")
        func_name = tool_name

        # 构建参数签名和调用参数
        sig = ", ".join(f'{p}: str = ""' for p in param_names) if param_names else ""
        safe_params = ", ".join(param_names) if param_names else ""

        # 动态生成函数代码
        call_part = f", {safe_params}" if safe_params else ""
        func_code = f'''
def {func_name}({sig}) -> str:
    """{description}"""
    return _call_textcli("{directive_id}"{call_part})
'''

        try:
            exec(func_code, tool_ns)
        except SyntaxError as e:
            logger.error("无法生成工具函数 %s: %s", tool_name, e)
            continue

        tool_func = tool_ns[func_name]
        tool_func.__doc__ = description

        # 注册到 FastMCP
        mcp.tool(name=tool_name, description=description)(tool_func)
        registered += 1
        logger.info(
            "MCP tool registered: %s(%s) → %s",
            tool_name, ", ".join(param_names) if param_names else "(无参数)",
            directive_id,
        )

    if skipped:
        logger.warning("MCP expose: %d 条指令未注册 — %s", len(skipped), ", ".join(skipped))

    return registered


# ── 启动入口 ──────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s:%(name)s:%(message)s",
    )

    logger.info("text-cli MCP Server v2 (配置驱动)")
    logger.info("  端口: %d → %s", MCP_PORT, SERVICE_URL)
    logger.info("  暴露配置: %s", EXPOSURE_PATH)
    logger.info("  Schema 目录: %s", SCHEMA_DIR)

    count = _register_tools()
    logger.info("已注册 %d 个 MCP 工具", count)

    if count == 0:
        logger.error("未注册任何 MCP 工具——请检查 mcp_exposure.json 和 service schema 目录")
        exit(1)

    mcp.run(transport="sse", host="0.0.0.0", port=MCP_PORT)
