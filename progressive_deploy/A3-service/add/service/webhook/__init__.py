"""
webhook — A3 骨架级通用 webhook 模块

让 A3 从"被动响应"变成"主动响应"。
外部事件源通过 POST /webhook/<provider> 通知 A3，A3 按声明式路由表执行指令链。

依赖: core/registry.py (dispatch), core/response.py (ok/error)
集成: main.py try/except import 后自动启用

阶段一: 骨架通用能力，不绑定任何 provider。
"""

import hashlib
import hmac
import json
import logging
import time
from pathlib import Path

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter()

# ── 内置验证器 ────────────────────────────

_VERIFIERS = {}


def register_verifier(name: str, fn):
    """注册验签函数。fn(provider_config, request, body_bytes) -> bool"""
    _VERIFIERS[name] = fn


def _verify_hmac_sha256(provider_config: dict, request: Request, body: bytes) -> bool:
    """HMAC-SHA256 验签。从 Header 取签名，与本地 secret 计算对比。"""
    header_name = provider_config.get("verify_params", {}).get("header", "X-Signature")
    sig = request.headers.get(header_name, "")
    if not sig:
        return False
    secret_ref = provider_config.get("verify_params", {}).get("secret_ref", "")
    if not secret_ref:
        return False
    # secret_ref 格式: "key:<key_name>"，暂用配置中的 secret 字段
    secret = provider_config.get("verify_params", {}).get("secret", "")
    if not secret:
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig)


def _verify_basic_token(provider_config: dict, request: Request, body: bytes) -> bool:
    """Bearer Token 验签。从 Authorization Header 取 token。"""
    auth = request.headers.get("Authorization", "")
    token = provider_config.get("verify_params", {}).get("token", "")
    if not token:
        return False
    return auth == f"Bearer {token}" or auth == token


register_verifier("hmac_sha256", _verify_hmac_sha256)
register_verifier("basic_token", _verify_basic_token)

# ── 内置事件解析器 ─────────────────────────

_PARSERS = {}


def register_parser(name: str, fn):
    """注册事件解析函数。fn(provider_config, request) -> dict"""
    _PARSERS[name] = fn


async def _parse_json_body(provider_config: dict, request: Request) -> dict:
    """解析 JSON body 事件。"""
    try:
        return await request.json()
    except Exception:
        return {}


register_parser("json_body", _parse_json_body)

# ── 路由表管理 ────────────────────────────

_ROUTES = []
_PROVIDERS = {}
_CONFIG_PATH = None


def load_routes(config_path: str = None):
    """从 config/webhook_routes.json 加载路由表和 provider 配置。"""
    global _ROUTES, _PROVIDERS, _CONFIG_PATH
    if config_path:
        _CONFIG_PATH = config_path
    if not _CONFIG_PATH:
        _CONFIG_PATH = str(Path(__file__).resolve().parent.parent / "config" / "webhook_routes.json")
    try:
        with open(_CONFIG_PATH, "r") as f:
            cfg = json.load(f)
        _ROUTES = cfg.get("routes", [])
        _PROVIDERS = cfg.get("providers", {})
        logger.info("webhook routes loaded: %d routes, %d providers", len(_ROUTES), len(_PROVIDERS))
    except FileNotFoundError:
        logger.info("webhook_routes.json not found, webhook endpoint disabled")
        _ROUTES = []
        _PROVIDERS = {}


# ── 指令执行 ──────────────────────────────

async def _execute_actions(actions: list) -> dict:
    """按顺序执行指令链。当前为线性同步执行。"""
    from core.registry import dispatch

    results = []
    for action in actions:
        directive = action.get("directive", "")
        params = action.get("params", [])
        try:
            # 解析指令
            parts = directive.split(";", 1)
            if len(parts) != 2:
                results.append({"directive": directive, "status": "error", "error": "invalid directive format"})
                continue
            domain, action_name = parts
            result = dispatch(domain, action_name, params)
            results.append({"directive": directive, "status": "ok", "result": str(result)[:500]})
        except Exception as e:
            results.append({"directive": directive, "status": "error", "error": str(e)})
    return results


# ── 路由处理 ──────────────────────────────

@router.api_route("/{provider:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def handle_webhook(provider: str, request: Request):
    """通用 webhook 入口。

    流程:
      ① 查 provider 配置 → 未注册返回 404
      ② 验签 → 失败返回 403
      ③ 解析事件 → 失败返回 400
      ④ 查路由表 → 未匹配返回 202 (accepted but no route)
      ⑤ 执行指令链 → 返回 200
    """
    provider = provider.rstrip("/")

    # ① 查 provider
    pconf = _PROVIDERS.get(provider)
    if not pconf:
        return JSONResponse(
            status_code=404,
            content={"error": f"unknown provider: {provider}", "provider": provider},
        )

    # ② 验签
    body = await request.body()
    verifier_name = pconf.get("verify", "")
    verifier = _VERIFIERS.get(verifier_name)
    if verifier:
        if not verifier(pconf, request, body):
            logger.warning("webhook verify failed: provider=%s, verifier=%s", provider, verifier_name)
            return JSONResponse(
                status_code=403,
                content={"error": "signature verification failed", "provider": provider},
            )

    # ③ 解析事件
    parser_name = pconf.get("parse", "json_body")
    parser = _PARSERS.get(parser_name, _parse_json_body)
    try:
        event = await parser(pconf, request)
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={"error": f"event parse failed: {e}", "provider": provider},
        )

    # ④ 查路由表
    matched_routes = []
    for route in _ROUTES:
        if route.get("provider") != provider:
            continue
        if route.get("event") and route["event"] != event.get("event", event.get("action", "")):
            continue
        # match 字段匹配
        match = route.get("match", {})
        matched = True
        for key, value in match.items():
            if event.get(key) != value:
                matched = False
                break
        if matched:
            matched_routes.append(route)

    if not matched_routes:
        return JSONResponse(
            status_code=202,
            content={"status": "accepted", "message": "no matching route", "provider": provider},
        )

    # ⑤ 执行指令链
    all_results = []
    for route in matched_routes:
        actions = route.get("actions", [])
        if route.get("async", False):
            # 异步模式：启动后台任务，立即返回 accepted
            import asyncio
            asyncio.ensure_future(_execute_actions(actions))
            all_results.append({"route": route.get("event", ""), "status": "accepted"})
        else:
            results = await _execute_actions(actions)
            all_results.append({"route": route.get("event", ""), "status": "ok", "results": results})

    return JSONResponse(
        status_code=200,
        content={"status": "ok", "provider": provider, "results": all_results},
    )


# ── 模块加载时自动加载路由表 ──────────────

load_routes()
