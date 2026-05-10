"""
Service proxy handler (base edition) — multi-source directive service dispatch

Directive:
  聚合;分发,<service_name>,<prompt>

Config:
  endpoints.json — defines target service list and routing rules
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

    service_rank: numeric rank or "auto" (first available)
    prompt: full text-cli directive text
    """
    if len(params) < 2:
        return error('missing_param', 'Need service_rank and prompt')

    rank = params[0]
    prompt = params[1]

    try:
        rank_int = int(rank)
    except ValueError:
        rank_int = None

    endpoints = _load_endpoints()
    if not endpoints:
        return error('no_endpoints', 'No endpoints configured')

    # Sort by rank, select matching endpoint
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

    return error('all_failed', 'All endpoints unavailable')
