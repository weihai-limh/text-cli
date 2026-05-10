"""
服务聚合 handler（基础版）— 多源指令服务分发

指令:
  聚合;分发,<service_name>,<prompt>

配置:
  endpoints.json — 定义目标服务列表和路由规则
"""

import json
import os
import urllib.request
from pathlib import Path

from core import ok, error

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "endpoints.json"


def _load_endpoints() -> list:
    if not CONFIG_PATH.exists():
        return []
    with open(CONFIG_PATH) as f:
        cfg = json.load(f)
    return cfg.get("endpoints", [])


def proxy_dispatch(params: list) -> dict:
    """
    聚合;分发,<service_rank>,<prompt>

    service_rank: 数字 rank 或 "auto"（自动选第一个可用）
    prompt: 完整 text-cli 指令文本
    """
    if len(params) < 2:
        return error('missing_param', '需要 service_rank 和 prompt')

    rank = params[0]
    prompt = params[1]

    try:
        rank_int = int(rank)
    except ValueError:
        rank_int = None

    endpoints = _load_endpoints()
    if not endpoints:
        return error('no_endpoints', '未配置任何端点')

    # 按 rank 排序，选匹配的端点
    sorted_ep = sorted(endpoints, key=lambda e: int(e.get('rank', 99)))

    for ep in sorted_ep:
        if rank_int is not None and int(ep.get('rank', 99)) != rank_int:
            continue
        try:
            url = ep.get('url', '')
            token = ep.get('token', '')
            req = urllib.request.Request(
                f"{url.rstrip('/')}/cli/text_cli",
                data=json.dumps({"prompt": prompt}).encode(),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": token,
                },
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        except Exception as e:
            print(f"[proxy] {ep.get('name')} failed: {e}")

    return error('all_failed', '所有端点均不可用')
