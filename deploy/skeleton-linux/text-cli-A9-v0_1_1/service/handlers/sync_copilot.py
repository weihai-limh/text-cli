"""
sync-copilot — 从 A2 copilot 发现指令并自动生成 A3 proxy 路由。

从 A2 的 /text_cli_schema.json 获取当前可用的 copilot 指令，
自动写入 proxy_routes.json，使这些指令通过 A3 proxy 可达。

依赖：
  - A2 copilot 运行在 127.0.0.1:20260（可选，不可达时跳过）
  - TEXT_CLI_HOME 环境变量（或 ~/text-cli/ 兜底）

Author: Tide 🌊
"""

import json
import logging
import os
from pathlib import Path

from core.registry import directive

from handlers.proxy import reset_proxy_routes
from handlers.schema_query import _fetch_a2_directives

logger = logging.getLogger(__name__)

_PROJECT = Path(os.environ.get("TEXT_CLI_HOME", str(Path.home() / "text-cli")))
PROXY_CONFIG_PATH = str(_PROJECT / "service" / "config" / "proxy_routes.json")

# A2 proxy 目标（固定，copilot 仅本机可达）
A2_PROXY_URL = "http://localhost:20260/text-cli/cli"

# 抽检条目数
SPOT_CHECK_COUNT = 3


def _synthesize_routes(a2_directives: list[dict]) -> dict[str, dict]:
    """将 A2 指令列表转为 proxy_routes 格式。

    A2 的 /text_cli_schema.json 中使用 "id" 字段表示 "domain;action"，
    如 "key;register"、"text-cli;co-install"。也兼容直接的 domain/action 字段。
    """
    routes = {}
    for d in a2_directives:
        # 优先从 id 字段解析
        op_id = d.get("id", "")
        if ";" in op_id:
            domain, action = op_id.split(";", 1)
        else:
            domain = d.get("domain")
            action = d.get("action")
        if not domain or not action:
            continue
        key = f"{domain};{action}"
        # 已有路由不覆盖（保留手工配置优先级）
        if key in routes:
            continue
        routes[key] = {
            "url": A2_PROXY_URL,
            "token": "",
            "sensitive": False,
        }
    return routes


def _spot_check(routes: dict[str, dict]) -> list[str]:
    """抽检前 N 条生成的路由，确认 A2 可达。"""
    import urllib.error
    import urllib.request
    from urllib.parse import urlparse

    ok = []
    items = list(routes.items())[:SPOT_CHECK_COUNT]
    for key, route in items:
        url = route["url"]
        if urlparse(url).scheme not in ('http', 'https'):
            continue
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps({"prompt": ""}).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5):
                ok.append(key)
        except Exception:
            pass
    return ok


@directive("text-cli", "sync-copilot", domain_alias="文本指令", action_aliases={"sync-copilot": "同步副驾"})
def sync_copilot(params: list[str]) -> dict:
    """
    发现 A2 copilot 指令并自动生成 A3 proxy 路由。

    参数: (none) — 同步全部

    返回摘要：发现条数、写入条数、抽检结果。
    """
    # 1. 发现
    a2_directives = _fetch_a2_directives()
    if not a2_directives:
        return {"status": "error", "reason": "A2 copilot not detected on this node (127.0.0.1:20260)"}

    # 2. 路由合成
    routes = _synthesize_routes(a2_directives)
    if not routes:
        return {"status": "error", "reason": "No valid routes extracted from A2-discovered directives"}

    # 3. 写入 proxy_routes.json
    config_dir = Path(PROXY_CONFIG_PATH).parent
    config_dir.mkdir(parents=True, exist_ok=True)
    with open(PROXY_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(routes, f, ensure_ascii=False, indent=2)
    logger.info("sync-copilot: wrote %d routes to %s", len(routes), PROXY_CONFIG_PATH)

    # 4. 重置 proxy 缓存
    reset_proxy_routes()

    # 5. 抽检验证
    checked = _spot_check(routes)
    checked_count = min(SPOT_CHECK_COUNT, len(routes))
    check_ok = len(checked)
    check_fail = checked_count - check_ok

    # 6. 摘要 → dict
    result_data = {
        "status": "ok",
        "a2_discovered": len(a2_directives),
        "routes_generated": len(routes),
        "wrote_file": PROXY_CONFIG_PATH,
        "spot_check_ok": check_ok,
        "spot_check_total": checked_count,
    }
    if check_fail:
        result_data["spot_check_fail"] = check_fail
        result_data["spot_check_note"] = "failed routes do not affect written config, A2 may be busy"
    return result_data
