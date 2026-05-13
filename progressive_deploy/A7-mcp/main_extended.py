"""
text-cli-service — A3 骨架 + A7 MCP 扩展版 main.py
基于 PR1 的 A3 骨架，叠加 MCP 路由能力。

新增：
  - SQLite 密钥管理
  - MCP dispatch（schema 派生路由）
  - MCP 优先路由 → 本地 dispatch → 代理转发

部署: 在 A3 骨架基础上，将 mcp_dispatch.py + mcp_handler.py 放入 core/ 和 handlers/，
      替换 main.py 为本文件。
"""

import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from core.parser import parse_directive, DirectiveParseError
from core.auth import verify_service_token
from core.registry import dispatch, get_registered_directives
from core.response import ok, error
from handlers.proxy import proxy_dispatch

LOG_LEVEL = os.getenv("LOG_LEVEL", "info").upper()
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))
logger = logging.getLogger(__name__)

SCHEMA_PATH = os.getenv(
    "SCHEMA_PATH",
    str(project_root / "config" / "text_cli_schema.json"),
)

# ── A6 SQLite ──
SQLITE_DB_PATH: dict | None = None
SQLITE_DB_FILE = os.getenv("SQLITE_DB_PATH", str(project_root / "data" / "service.db"))

try:
    from text_cli_modules.sqlite import init_db
    db_dir = Path(SQLITE_DB_FILE).parent
    db_dir.mkdir(parents=True, exist_ok=True)
    init_db(SQLITE_DB_FILE)
    SQLITE_DB_PATH = {'config': SQLITE_DB_FILE}
    logger.info("SQLite 已初始化: %s", SQLITE_DB_FILE)
except ImportError:
    logger.info("SQLite 模块未安装（A6 可选）")
except Exception as e:
    logger.warning("SQLite 初始化失败: %s", e)

_schema: dict[str, dict] = {}
_copilot_token: str = ""


def _load_schema():
    global _schema
    if not os.path.exists(SCHEMA_PATH):
        logger.warning("Schema not found: %s", SCHEMA_PATH)
        _schema = {}
        return
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        _schema = json.load(f)
    logger.info("Loaded %d directives from %s", len(_schema), SCHEMA_PATH)
    # ── A7 MCP 路由初始化 ──
    try:
        from core.mcp_dispatch import init_from_schema
        init_from_schema(_schema)
        logger.info("MCP 路由表已初始化")
    except ImportError:
        logger.info("MCP dispatch 未安装（A7 可选）")


def _load_copilot_token():
    global _copilot_token
    try:
        route_path = os.path.join(os.path.dirname(__file__), "config", "proxy_routes.json")
        with open(route_path, "r") as f:
            routes = json.load(f)
        for route in routes.values():
            if isinstance(route, dict) and route.get("token"):
                _copilot_token = route["token"]
                break
        logger.info("Copilot token loaded")
    except Exception as e:
        logger.warning("Failed to load copilot token: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    import handlers  # noqa: F401
    _load_copilot_token()
    _load_schema()
    registered = get_registered_directives()
    logger.info("Registered handlers: %s", registered)
    yield
    logger.info("Shutting down.")


app = FastAPI(
    title="text-cli 指令服务（A3 + A7）",
    description="A3 骨架 + MCP 路由扩展",
    version="0.2.0",
    lifespan=lifespan,
)


@app.get("/text_cli_schema.json")
async def get_schema():
    return JSONResponse(content=_schema)


@app.get("/cache/{key}")
async def image_cache_retrieve(key: str):
    from handlers.image import cache_get
    data = cache_get(key)
    if data is None:
        return JSONResponse(
            status_code=410,
            content={"rst_types": "text", "rst_data": {"text": "缓存已过期或不存在"},
                      "rst_err": "cache_expired"},
        )
    return Response(content=data, media_type="text/plain; charset=utf-8")


@app.get("/health")
async def health():
    directives = get_registered_directives()
    info = {"status": "ok", "directives": directives}
    if SQLITE_DB_PATH:
        info["sqlite"] = "enabled"
    return info


@app.post("/cli/text_cli")
async def handle_directive(request: Request):
    service_token = request.headers.get("Service-token")
    auth = verify_service_token(service_token)
    if not auth.allowed:
        return JSONResponse(status_code=403, content=error(auth.message))

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content=error("请求体不是有效 JSON"))

    prompt = body.get("prompt")
    if not prompt:
        return JSONResponse(status_code=400, content=error("缺少 prompt 字段"))

    try:
        parsed = parse_directive(prompt)
    except DirectiveParseError as e:
        return JSONResponse(status_code=400, content=error(f"{e.code}: {e.message}"))

    logger.info("收到指令: %s;%s, 参数: %s", parsed.domain, parsed.action, parsed.params)

    # ── A7 MCP 路由（优先 + 后备） ──
    try:
        from core.mcp_dispatch import decide_backend, get_mcp_route, adapt_params
        backend = decide_backend(parsed.domain, parsed.action)

        if backend == "mcp":
            mcp_route = get_mcp_route(parsed.domain, parsed.action)
            if mcp_route:
                try:
                    from handlers.mcp_handler import call_mcp_tool, format_mcp_result
                    args = adapt_params(parsed.params, mcp_route)
                    mcp_result = call_mcp_tool(
                        mcp_route["server"], mcp_route["tool"],
                        args, timeout_ms=mcp_route.get("timeout_ms", 30000)
                    )
                    if mcp_result["ok"]:
                        return ok(format_mcp_result(mcp_result))
                    return JSONResponse(
                        status_code=502,
                        content=error(f"MCP 调用失败: {mcp_result['error']}"),
                    )
                except ImportError:
                    return JSONResponse(status_code=500, content=error("MCP handler 不可用"))
    except ImportError:
        pass

    # 1. 本地 dispatch
    result = dispatch(parsed.domain, parsed.action, parsed.params)
    if result and '未找到匹配的指令' not in result:
        return ok(result)

    # 2. MCP 后备路由
    try:
        from core.mcp_dispatch import get_mcp_route, adapt_params
        mcp_route = get_mcp_route(parsed.domain, parsed.action)
        if mcp_route:
            from handlers.mcp_handler import call_mcp_tool, format_mcp_result
            args = adapt_params(parsed.params, mcp_route)
            mcp_result = call_mcp_tool(
                mcp_route["server"], mcp_route["tool"],
                args, timeout_ms=mcp_route.get("timeout_ms", 30000)
            )
            if mcp_result["ok"]:
                return ok(format_mcp_result(mcp_result))
    except ImportError:
        pass

    # 3. 代理转发
    proxy_result = proxy_dispatch(parsed.domain, parsed.action,
                                  parsed.params, raw_prompt=prompt,
                                  db_path=SQLITE_DB_PATH)
    if proxy_result is not None:
        return JSONResponse(content=proxy_result)

    # 4. 无匹配
    return ok(result)


@app.api_route("/text-cli-copilot/{rest:path}", methods=["GET", "POST"])
async def copilot_proxy(request: Request, rest: str):
    import urllib.request, urllib.error
    target = f"http://localhost:20260/{rest}"
    qs = str(request.query_params)
    if qs:
        target += "?" + qs
    body = await request.body() if request.method == "POST" else None
    req = urllib.request.Request(
        target, data=body,
        headers={
            "Authorization": f"Bearer {_copilot_token}",
            "Content-Type": request.headers.get("Content-Type", "application/json"),
        },
        method=request.method,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read()
            ct = resp.headers.get("Content-Type", "application/octet-stream")
            return Response(content=content, media_type=ct, status_code=resp.status)
    except urllib.error.HTTPError as e:
        logger.error("copilot proxy error: %s -> %d", rest, e.code)
        return JSONResponse(
            status_code=e.code,
            content={"rst_types": "text", "rst_data": {"text": f"[proxy] copilot 返回 {e.code}"}},
        )
    except Exception as e:
        logger.error("copilot proxy failed: %s", e)
        return JSONResponse(
            status_code=502,
            content={"rst_types": "text", "rst_data": {"text": f"[proxy] {e}"}},
        )


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "28050"))
    uvicorn.run(app, host="0.0.0.0", port=port)
