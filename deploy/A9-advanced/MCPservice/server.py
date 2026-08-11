"""
text-cli MCP Server — 将 text-cli 热指令暴露为 MCP tools

基于 FastMCP，从 service_manifest.json 读取暴露白名单、
从 handlers/schema/*.json 读取指令定义，动态生成 MCP 工具函数。

启动后，任何 MCP 客户端（Claude Desktop / Cursor / mcporter）
都可以通过标准 MCP 协议发现和调用 text-cli 指令。

架构：
  MCP 客户端 ←→ FastMCP (port 9020) ←→ text-cli-service (port 28050)

配置：
  统一走 A3 core/config.py 的 load_config() → mcp 段。
  暴露白名单：service_manifest.json → public_directives（与 /skills 面同源）。

Author: Tide 🌊 · 2026-05-14 · v2 配置驱动重写 → 2026-08-03 合并+守护钩子
"""

import json
import logging
import os
import pathlib
import re
import sys
import threading

import requests
from fastmcp import FastMCP

# ── FastMCP 实例 ──────────────────────────────────

mcp = FastMCP("text-cli")
logger = logging.getLogger("textcli_mcp")

# ── 运行时注入（由 main.py 守护钩子或 start_outbound 设置）──

_service_url = ""
_service_token = ""
_schema_dir = None


def _call(directive: str, *params: str) -> str:
    """调用 text-cli-service 并返回 rst_data 内容。"""
    parts = [directive]
    parts.extend(str(p) for p in params if p)
    prompt = "AI:" + ",".join(parts)

    try:
        resp = requests.post(
            _service_url,
            json={"prompt": prompt},
            headers={"Service-token": _service_token},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        rst_data = data.get("rst_data", {})
        text = json.dumps(rst_data, ensure_ascii=False) if rst_data else ""
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
        return "[MCP bridge error] request timeout (60s)"
    except requests.exceptions.ConnectionError:
        return f"[MCP bridge error] cannot connect to text-cli-service ({_service_url})"
    except Exception as e:
        return f"[MCP bridge error] {e}"


# ── 暴露白名单 — service_manifest.json ─────────────

def _load_manifest() -> list[str]:
    """从 service_manifest.json 读取暴露白名单（domain;action 数组）。"""
    text_cli_home = os.environ.get("TEXT_CLI_HOME", "")
    if not text_cli_home:
        logger.warning("TEXT_CLI_HOME 未设置，无法读取 service_manifest.json")
        return []
    manifest_path = pathlib.Path(text_cli_home) / "service" / "config" / "service_manifest.json"
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        directives = cfg.get("public_directives", [])
        if not directives:
            logger.info("service_manifest.public_directives 为空，不暴露任何 MCP 工具")
        return directives
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning("无法加载 service_manifest.json: %s", e)
        return []


# ── schema 加载 ────────────────────────────────────

def _load_schema_map() -> dict[str, dict]:
    """加载 service 的指令 schema，构建 {domain;action: directive_def} 映射。

    读取 handlers/schema/*.json，提取 directives 数组中的每一条，
    同时注册中英文变体到同一映射。
    """
    if _schema_dir is None:
        return {}
    schema_map: dict[str, dict] = {}

    if not _schema_dir.exists():
        logger.warning("Schema 目录不存在: %s", _schema_dir)
        return schema_map

    for sf in sorted(_schema_dir.glob("*_schema.json")):
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
            dc = d.get("domain_zh", "")
            ac = d.get("action_zh", "")
            if dc and ac and f"{dc};{ac}" != key:
                schema_map[f"{dc};{ac}"] = d

    return schema_map


# ── 参数名提取 ────────────────────────────────────

_PARAM_NAME_RE = re.compile(r"<(\w+)>")
_PARAM_SANITIZE_RE = re.compile(r"[^\w]")

_PYTHON_KEYWORDS = frozenset({
    "from", "import", "class", "def", "if", "else", "elif",
    "for", "while", "try", "except", "finally", "with", "as",
    "return", "yield", "lambda", "and", "or", "not", "in", "is",
    "True", "False", "None", "pass", "break", "continue", "raise",
    "global", "nonlocal", "assert", "del", "async", "await",
    "type",
})


def _extract_param_names(directive_def: dict) -> list[str]:
    """从指令定义中提取 MCP 工具参数名。"""
    usage = directive_def.get("usage", "")
    names = _PARAM_NAME_RE.findall(usage)
    if names:
        sanitized = []
        for n in names:
            n = _PARAM_SANITIZE_RE.sub("_", n)
            if n in _PYTHON_KEYWORDS:
                n = f"{n}_"
            sanitized.append(n)
        return sanitized

    params = directive_def.get("params", [])
    return [f"param_{i + 1}" for i in range(len(params))]


# ── 动态工具注册 ──────────────────────────────────

def _register_tools() -> int:
    """从 service_manifest 白名单和 schema 动态注册 MCP 工具。

    使用 exec() 动态生成带显式参数签名的工具函数，
    因为 FastMCP 不支持 **kwargs。
    """
    exposure = _load_manifest()
    schema_map = _load_schema_map()

    registered = 0
    skipped = []
    tool_ns = {"_call": _call}

    for directive_id in exposure:
        directive_def = schema_map.get(directive_id)
        if directive_def is None:
            skipped.append(directive_id)
            logger.warning("MCP expose: 指令未在 schema 中找到 — %s", directive_id)
            continue

        param_names = _extract_param_names(directive_def)
        domain = directive_def.get("domain", "")
        action = directive_def.get("action", "")
        description = directive_def.get("description_zh", directive_def.get("description", ""))

        tool_name = f"{domain}_{action}".replace("-", "_").replace(".", "_")
        func_name = tool_name

        sig = ", ".join(f'{p}: str = ""' for p in param_names) if param_names else ""
        safe_params = ", ".join(param_names) if param_names else ""

        call_part = f", {safe_params}" if safe_params else ""
        func_code = f'''
def {func_name}({sig}) -> str:
    """{description}"""
    return _call("{directive_id}"{call_part})
'''

        try:
            exec(func_code, tool_ns)
        except SyntaxError as e:
            logger.error("无法生成工具函数 %s: %s", tool_name, e)
            continue

        tool_func = tool_ns[func_name]
        tool_func.__doc__ = description

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


# ── 守护钩子入口（由 main.py lifespan 调用）────────

def start_outbound():
    """启动 outbound MCP 桥（由 main.py lifespan 守护钩子调用）。

    从 A3 core/config.py 的 load_config() 读取 mcp 段配置；
    空 token 拒绝启动；暴露白名单来自 service_manifest.json。
    mcp.run 为阻塞调用 → 后台 daemon 线程常驻。
    """
    global _service_url, _service_token, _schema_dir

    # 延迟 import：确保在 main.py 的 sys.path 上下文中加载
    from core.config import load_config
    config = load_config()
    token = config["mcp"]["service_token"]
    if not token:
        raise RuntimeError("mcp.service_token 未配置，拒绝启动 A7 outbound")

    _service_token = token
    _service_url = config["mcp"]["service_url"] or "http://localhost:28050/text-cli/cli"
    port = config["mcp"]["port"]

    text_cli_home = os.environ.get("TEXT_CLI_HOME", "")
    if text_cli_home:
        _schema_dir = pathlib.Path(text_cli_home) / "service" / "handlers" / "schema"

    count = _register_tools()
    if count == 0:
        logger.warning("A7 outbound 暴露 0 个工具（请检查 service_manifest.public_directives）")
    else:
        logger.info("A7 outbound 已注册 %d 个 MCP 工具", count)

    t = threading.Thread(
        target=mcp.run,
        kwargs={"transport": "sse", "host": "0.0.0.0", "port": port},
        daemon=True,
    )
    t.start()
    logger.info("A7 outbound MCP bridge started on 0.0.0.0:%d", port)
    return t


# ── 手动调试入口（非正式启动路径）───────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s:%(name)s:%(message)s",
    )
    logger.info("text-cli MCP Server (manual debug mode)")

    # 调试模式：从环境变量读配置
    _service_token = os.environ.get("TEXTCLI_SERVICE_TOKEN", "")
    if not _service_token:
        logger.error("TEXTCLI_SERVICE_TOKEN 未设置")
        sys.exit(1)
    _service_url = os.environ.get("TEXTCLI_SERVICE_URL", "http://localhost:28050/text-cli/cli")
    port = int(os.environ.get("MCP_PORT", "9020"))

    text_cli_home = os.environ.get("TEXT_CLI_HOME", str(pathlib.Path.home() / "text-cli"))
    _schema_dir = pathlib.Path(text_cli_home) / "service" / "handlers" / "schema"

    count = _register_tools()
    logger.info("已注册 %d 个 MCP 工具", count)
    if count == 0:
        logger.error("未注册任何 MCP 工具——请检查 service_manifest.public_directives 和 schema 目录")
        sys.exit(1)

    mcp.run(transport="sse", host="0.0.0.0", port=port)
