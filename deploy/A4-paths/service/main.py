import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

logger = logging.getLogger(__name__)

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

project_root = Path(__file__).parent
if not os.environ.get("TEXT_CLI_HOME"):
    os.environ["TEXT_CLI_HOME"] = str(project_root.parent)
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# text-cli-modules 路径（与 service 同级）
_modules_root = Path(__file__).resolve().parent / "text_cli_modules"
if str(_modules_root.parent) not in sys.path:
    sys.path.append(str(_modules_root.parent))

from core.auth import verify_service_token
from core.parser import DirectiveParseError, parse_directive
from core.registry import dispatch, get_registered_directives
from core.response import error, ok
from handlers.proxy import proxy_dispatch

LOG_LEVEL = os.getenv("LOG_LEVEL", "info").upper()
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))
logger = logging.getLogger(__name__)


def _resolve_config_path(path: str) -> str:
    if os.path.exists(path):
        return path
    example_path = path.replace('.json', '.example.json')
    if os.path.exists(example_path):
        logger.info("Using example config: %s", example_path)
        return example_path
    return path


SCHEMA_PATH = os.getenv(
    "SCHEMA_PATH",
    str(project_root / "config" / "text_cli_schema.json"),
)

# ── 聚合指令加载 ──────────────────────────────

_aggregates: dict[str, dict] = {}
_AGGREGATE_DIR = Path(os.environ.get("AGGREGATE_DIR",
    str(project_root.parent / "A8-discovery" / "aggregate")))


def _load_aggregates():
    """启动时扫描 aggregate/*.json，加载聚合路由表。"""
    if not _AGGREGATE_DIR.exists():
        return
    for f in _AGGREGATE_DIR.glob("*.json"):
        try:
            agg = json.loads(f.read_text(encoding="utf-8"))
            if agg.get("type") != "aggregate":
                continue
            domain = agg["domain"]
            _aggregates[domain] = agg
            logger.info("aggregates loaded: %s (%d providers)", domain, len(agg.get("providers", {})))
        except Exception as e:
            logger.warning("Failed to load aggregate %s: %s", f.name, e)


def _aggregate_dispatch(domain: str, action: str, params: list) -> str | None:
    """聚合指令降级链调度。返回结果字符串或 None(未命中)。"""
    agg = _aggregates.get(domain)
    if not agg:
        return None

    # 检查 action 是否有 provider 映射
    providers_order = list(agg.get("default", []))

    # 用户显性指定提供方？(末参数匹配 provider 名)
    if params and params[-1] in agg.get("providers", {}):
        providers_order = [params.pop()]

    for provider_name in providers_order:
        provider = agg["providers"].get(provider_name, {})
        directive = provider.get(action)
        if not directive:
            continue  # 此提供方不支持此 action
        # directive 格式: "tx-map;geocode" 或 "tencent-maps;geocode"
        parts = directive.split(";", 1)
        if len(parts) != 2:
            continue
        p_domain, p_action = parts
        try:
            result = dispatch(p_domain, p_action, list(params))
            if result and "未找到匹配的指令" not in result and "No matching directive" not in result:
                # 检查是否配额耗尽或其他软错误
                try:
                    rj = json.loads(result)
                    if rj.get("status") == "stop":
                        logger.info("aggregate degrade: %s;%s quota exhausted, trying next", p_domain, p_action)
                        continue
                    if rj.get("status") == "error":
                        logger.info("aggregate degrade: %s;%s returned error, trying next", p_domain, p_action)
                        continue
                except (json.JSONDecodeError, TypeError):
                    pass
                logger.info("aggregate hit: %s → %s;%s", domain, p_domain, p_action)
                return result
        except Exception as e:
            logger.info("aggregate degrade: %s;%s exception %s, trying next", p_domain, p_action, e)
            continue

    return None

# ── 内部 dispatch (供 key_registry 和 mcp_handler 配额检查调用) ──

def _internal_dispatch(domain: str, action: str, params: list) -> dict | None:
    """框架内 dispatch → JSON 结果解析 → dict 返回。"""
    try:
        result_str = dispatch(domain, action, params)
    except Exception as e:
        logger.debug("dispatch error for %s;%s: %s", domain, action, e)
        return None
    try:
        result = json.loads(result_str)
        return result if isinstance(result, dict) else None
    except (json.JSONDecodeError, TypeError):
        return None


# SQLite 模块检测
SQLITE_DB_PATH: dict | None = None
SQLITE_DB_FILE = os.getenv(
    "SQLITE_DB_PATH",
    str(_modules_root / "sqlite" / "service.db"),
)

try:
    from text_cli_modules.sqlite import init_db
    db_dir = Path(SQLITE_DB_FILE).parent
    db_dir.mkdir(parents=True, exist_ok=True)
    init_db(SQLITE_DB_FILE)
    SQLITE_DB_PATH = {'config': SQLITE_DB_FILE}

    # 通知各 handler SQLite 路径
    _ARG_MAP = {
        "db": SQLITE_DB_FILE,
        "quota": str(_modules_root / "sqlite" / "quota.db"),
        "db_dict": SQLITE_DB_PATH,
        "project_root": str(project_root),
    }

    try:
        from config.handler_inits import DISPATCH_INJECTS, HANDLER_INITS
    except ImportError:
        HANDLER_INITS, DISPATCH_INJECTS = [], []

    for mod_path, fn_name, arg_key, _ in HANDLER_INITS:
        try:
            mod = __import__(mod_path, fromlist=[fn_name])
            init_fn = getattr(mod, fn_name)
            if arg_key:
                init_fn(_ARG_MAP[arg_key])
            else:
                init_fn()
            logger.info("%s initialised", mod_path)
        except Exception as e:
            logger.warning("Failed to init %s: %s", mod_path, e)

    for mod_path, setter_fn in DISPATCH_INJECTS:
        try:
            mod = __import__(mod_path, fromlist=[setter_fn])
            fn = getattr(mod, setter_fn)
            fn(_internal_dispatch)
            logger.info("%s dispatch injected", mod_path)
        except Exception as e:
            logger.warning("Failed to inject dispatch for %s: %s", mod_path, e)

    logger.info("SQLite module initialized: %s", SQLITE_DB_FILE)
except ImportError:
    logger.info("SQLite module not installed")
except Exception as e:
    logger.warning("SQLite initialization failed: %s", e)

# ── 聚合指令加载（平台级，不依赖 SQLite）──
_load_aggregates()

_schema: dict[str, dict] = {}
_copilot_token: str = ""


def _load_schema():
    global _schema
    if not os.path.exists(SCHEMA_PATH):
        logger.warning("Schema not found: %s", SCHEMA_PATH)
        _schema = {}
        return
    schema_path = _resolve_config_path(SCHEMA_PATH)
    with open(schema_path, "r", encoding="utf-8") as f:
        _schema = json.load(f)
    logger.info("Loaded %d directives from %s", len(_schema), SCHEMA_PATH)
    # 从 schema 派生 MCP 路由表（与 copilot _build_mcp_registry 同构）
    from core.mcp_dispatch import init_from_schema
    init_from_schema(_schema)


def _load_copilot_token():
    global _copilot_token
    try:
        route_path = _resolve_config_path(os.path.join(os.path.dirname(__file__), "config", "proxy_routes.json"))
        with open(route_path, "r") as f:
            routes = json.load(f)
        # 从任一路由取 copilot token
        for route in routes.values():
            if isinstance(route, dict) and route.get("token"):
                _copilot_token = route["token"]
                break
        logger.info("Copilot token loaded")
    except Exception as e:
        logger.warning("Failed to load copilot token: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    import handlers  # noqa: F401 — triggers auto-registration
    _load_copilot_token()
    _load_schema()
    try:
        from core.stream_subscriber_registry import init_subscribers
        init_subscribers()
    except ImportError:
        logger.info("stream_subscriber_registry not available, skipping")
    registered = get_registered_directives()
    logger.info("Registered handlers: %s", registered)
    yield
    logger.info("Shutting down.")


app = FastAPI(
    title="text-cli sample directive service",
    description="text-cli standard directive service template, integratable with Service_endpoint",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/text_cli_schema.json")
async def get_schema():
    return JSONResponse(content=_schema)


@app.get("/cache/{key}")
async def image_cache_retrieve(key: str):
    """获取缓存的 base64 图片数据"""
    try:
        from packages.image.handler import cache_get
    except ImportError:
        return JSONResponse(content={"status": "error", "reason": "image package not installed"}, status_code=503)
    data = cache_get(key)
    if data is None:
        return JSONResponse(
            status_code=410,
            content={"rst_types": "text", "rst_data": {"text": "cache expired or not found"},
                      "rst_err": "cache_expired"},
        )
    return Response(content=data, media_type="text/plain; charset=utf-8")


@app.get("/text-cli/health")
async def health(request: Request):
    directives = get_registered_directives()

    # Check if authenticated (for extended capabilities view)
    service_token = request.headers.get("Service-token")
    auth = verify_service_token(service_token)

    if auth.allowed:
        # Authenticated: full capabilities snapshot
        installed = []
        schema_dir = __import__('pathlib').Path(__file__).parent / "handlers" / "schema"
        for sf in sorted(schema_dir.glob("*_schema.json")):
            try:
                s = __import__('json').loads(sf.read_text(encoding="utf-8"))
                installed.append(s.get("id", sf.stem.replace("_schema", "")))
            except Exception as e:
                logger.warning("Failed to parse schema %s: %s", sf.name, e)

        return {
            "status": "ok",
            "body": os.getenv("TEXT_CLI_INSTANCE_ID", "text-cli"),
            "version": "1.0.0",
            "capabilities": {
                "packages": [p for p in installed if p not in ("sample",)],
                "domains": sorted(directives.keys()),
                "runtimes": ["python", "node", "mcp", "cmd"],
            },
            "endpoints": {
                "skills": "/text-cli/skills",
                "stct": "/text-cli/stct",
            },
            "sqlite": "enabled" if SQLITE_DB_PATH else None,
        }

    # Public: minimal info
    try:
        from handlers.skill_endpoint import list_skills
        skills = list_skills()
        public_count = sum(
            1 for v in skills.values()
            if isinstance(v, dict) and v.get("visibility") == "public"
        )
    except (ImportError, Exception):
        public_count = 0

    return {
        "status": "ok",
        "body": os.getenv("TEXT_CLI_INSTANCE_ID", "text-cli"),
        "version": "1.0.0",
        "public_skills": public_count,
    }


@app.get("/text-cli/stct")
async def stct():
    """暖空间 — 动态指令目录（纯文本，供 Agent 消费）"""
    from handlers.schema_query import schema_query
    text = schema_query([])  # 默认全量纯文本
    return Response(content=text, media_type="text/plain; charset=utf-8")


@app.post("/text-cli/cli")
async def handle_directive(request: Request):
    service_token = request.headers.get("Service-token")
    _identity_header = request.headers.get("X-Text-CLI-Identity")
    import time
    _req_start = time.time()
    auth = verify_service_token(service_token)
    if not auth.allowed:
        return JSONResponse(
            status_code=403,
            content=error(auth.message),
        )

    # 注入 identity_code 到异步安全上下文（供 handler 读取）
    from core.identity_context import _IDENTITY_CTX as _identity_ctx
    _identity_ctx.set(auth.identity_code)

    try:
        body = await request.json()
    except (json.JSONDecodeError, TypeError) as e:
        logger.debug("Invalid JSON in request body: %s", e)
        return JSONResponse(
            status_code=400,
            content=error("request body is not valid JSON"),
        )

    prompt = body.get("prompt")
    if not prompt:
        return JSONResponse(
            status_code=400,
            content=error("missing prompt field"),
        )

    try:
        parsed = parse_directive(prompt)
    except DirectiveParseError as e:
        return JSONResponse(
            status_code=400,
            content=error(f"{e.code}: {e.message}"),
        )

    logger.info(
        "收到指令: %s;%s, 参数: %s",
        parsed.domain, parsed.action, parsed.params,
    )

    # 0. 聚合指令优先（降级链多提供方调度）
    agg_result = _aggregate_dispatch(parsed.domain, parsed.action, parsed.params)
    if agg_result is not None:
        response = ok(agg_result)
        _write_call_log(request, auth, parsed, _req_start, True)
        return response

    # 1. MCP 优先路由（显式偏好 mcp 时优先）
    from core.mcp_dispatch import adapt_params, decide_backend, get_mcp_route
    try:
        from packages.mcp.handler import check_mcp_quota
    except ImportError:
        check_mcp_quota = None
    backend = decide_backend(parsed.domain, parsed.action)

    if backend == "mcp":
        mcp_route = get_mcp_route(parsed.domain, parsed.action)
        if mcp_route:
            # Quota check before MCP call
            quota_block = check_mcp_quota(
                mcp_route["server"], tool=mcp_route.get("tool", ""), dispatch_fn=_internal_dispatch
            )
            if quota_block:
                return JSONResponse(
                    status_code=429,
                    content=ok(json.dumps({"status": "quota_exceeded", **quota_block}, ensure_ascii=False)),
                )
            try:
                from packages.mcp.handler import call_mcp_tool, format_mcp_result
                args = adapt_params(parsed.params, mcp_route)
                mcp_result = call_mcp_tool(
                    mcp_route["server"], mcp_route["tool"],
                    args, timeout_ms=mcp_route.get("timeout_ms", 30000)
                )
                if mcp_result["ok"]:
                    return ok(format_mcp_result(mcp_result))
                elif mcp_result.get("degrade"):
                    logger.info("MCP preferred but unavailable for %s;%s, falling through to local",
                                parsed.domain, parsed.action)
                else:
                    return JSONResponse(
                        status_code=502,
                        content=error(f"MCP call failed: {mcp_result['error']}"),
                    )
            except ImportError:
                return JSONResponse(
                    status_code=500,
                    content=error("MCP handler unavailable"),
                )
        else:
            return JSONResponse(
                status_code=400,
                content=error(f"directive has no MCP route configured: {parsed.domain};{parsed.action}"),
            )

    # 2. 本地 dispatch
    result = dispatch(parsed.domain, parsed.action, parsed.params)
    local_handled = bool(result) and '未找到匹配的指令' not in result and 'No matching directive' not in result

    if local_handled:
        return ok(result)

    # 3. 本地未匹配 → 尝试 MCP（作为后备路由）
    mcp_route = get_mcp_route(parsed.domain, parsed.action)
    if mcp_route:
        # Quota check before MCP fallback call
        quota_block = check_mcp_quota(
            mcp_route["server"], tool=mcp_route.get("tool", ""), dispatch_fn=_internal_dispatch
        )
        if quota_block:
            return JSONResponse(
                status_code=429,
                content=ok(json.dumps({"status": "quota_exceeded", **quota_block}, ensure_ascii=False)),
            )
        try:
            from packages.mcp.handler import call_mcp_tool, format_mcp_result
            args = adapt_params(parsed.params, mcp_route)
            mcp_result = call_mcp_tool(
                mcp_route["server"], mcp_route["tool"],
                args, timeout_ms=mcp_route.get("timeout_ms", 30000)
            )
            if mcp_result["ok"]:
                return ok(format_mcp_result(mcp_result))
        except ImportError:
            pass

    # 4. 本地和 MCP 都没匹配 → 尝试代理转发
    proxy_result = proxy_dispatch(parsed.domain, parsed.action,
                                  parsed.params, raw_prompt=prompt,
                                  db_path=SQLITE_DB_PATH)
    if proxy_result is not None:
        # 旁路通知 stream subscriber
        from core.stream_subscriber_registry import STREAM_SUBSCRIBERS
        if STREAM_SUBSCRIBERS:
            try:
                text = proxy_result.get("rst_data", {}).get("text", "")
                if isinstance(text, dict):
                    text = json.dumps(text, ensure_ascii=False)
                im_target = body.get("_im_to_user", "")
                im_session = body.get("_im_session", "")
                if im_target and text and im_session:
                    for sub in STREAM_SUBSCRIBERS:
                        try:
                            await sub.on_end(im_session, im_target, str(text))
                        except Exception as e:
                            logger.debug("Stream subscriber on_end failed: %s", e)
                            pass
            except Exception as e:
                logger.debug("IM proxy send failed: %s", e)
                pass
        return JSONResponse(content=proxy_result)

    # 5. 都没有 → 返回本地结果
    response = ok(result)
    _write_call_log(request, auth, parsed, _req_start, True)
    return response


# ── Skills 发现与执行端点 ──

@app.get("/text-cli/skills")
async def skills_list():
    """列出所有对外暴露的技能（public + restricted）"""
    try:
        from handlers.skill_endpoint import list_skills
        return JSONResponse(content=list_skills())
    except ImportError:
        return JSONResponse(content={"skills": []})


@app.get("/text-cli/skills/{skill_id}")
async def skills_detail(skill_id: str):
    """获取单个技能的完整详情"""
    try:
        from handlers.skill_endpoint import get_skill_detail
    except ImportError:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "error": "unavailable",
                      "message": "skill endpoint not ready"},
        )
    detail = get_skill_detail(skill_id)
    if detail is None:
        return JSONResponse(
            status_code=404,
            content={"status": "error", "error": "not_found",
                      "message": f"skill '{skill_id}' not found or not exposed"},
        )
    return JSONResponse(content=detail)


@app.post("/text-cli/skills/{skill_id}")
async def skills_execute(skill_id: str, request: Request):
    """Execute a skill via the path engine."""
    try:
        from handlers.skill_endpoint import get_skill_detail
    except ImportError:
        return JSONResponse(
            status_code=503,
            content={"rst_types": "text", "rst_data": {"text": "skill endpoint not ready"},
                      "rst_err": "ERR_EXECUTION"},
        )

    detail = get_skill_detail(skill_id)
    if detail is None:
        return JSONResponse(
            status_code=404,
            content={"rst_types": "text", "rst_data": {"text": f"skill '{skill_id}' not found"},
                      "rst_err": "ERR_NOT_FOUND"},
        )

    body = await request.json() if request.headers.get("content-type") == "application/json" else {}
    skill_input = body.get("input", {}) if isinstance(body, dict) else {}
    from core.registry import dispatch as _dispatch
    directive = detail.get("directive") or "text-cli;path"
    params = [str(v) for v in skill_input.values()] if skill_input else []
    result = _dispatch(directive, "", params)
    return JSONResponse(content=json.loads(result) if isinstance(result, str) else result)


@app.api_route("/text-cli-copilot/{rest:path}", methods=["GET", "POST"])
async def copilot_proxy(request: Request, rest: str):
    """通配代理 — 透传所有请求到 copilot:20260"""
    import httpx

    target = f"http://localhost:20260/{rest}"
    qs = str(request.query_params)
    if qs:
        target += "?" + qs

    body = await request.body() if request.method == "POST" else None

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.request(
                request.method, target,
                content=body,
                headers={
                    "Authorization": f"Bearer {_copilot_token}",
                    "Content-Type": request.headers.get("Content-Type", "application/json"),
                },
                timeout=30,
            )
            return Response(
                content=resp.content,
                media_type=resp.headers.get("Content-Type", "application/octet-stream"),
                status_code=resp.status_code,
            )
    except httpx.HTTPStatusError as e:
        logger.error("copilot proxy error: %s -> %d", rest, e.response.status_code)
        return JSONResponse(
            status_code=e.response.status_code,
            content={"rst_types": "text", "rst_data": {"text": f"[proxy] copilot returned {e.response.status_code}"},
                      "rst_err": "proxy_error"},
        )
    except Exception as e:
        logger.error("copilot proxy failed: %s", e)
        return JSONResponse(
            status_code=502,
            content={"rst_types": "text", "rst_data": {"text": f"[proxy] {e}"},
                      "rst_err": "proxy_error"},
        )


# ── Webhook 路由 ──

try:
    from webhook import router as webhook_router
    app.include_router(webhook_router, prefix="/webhook")
except ImportError:
    logger.info("webhook module not installed, /webhook endpoint disabled")


# ── 调用审计辅助函数 ──────────────────────

def _write_call_log(request: Request, auth, parsed, req_start: float,
                    success: bool) -> None:
    """在请求完成后写入审计日志。受 A3_COUNT_CALLS 控制。"""
    import time
    try:
        from core.auth import write_call_log
        domain = parsed.domain if parsed else (
            getattr(request.state, '_last_domain', '') if hasattr(request.state, '_last_domain') else ''
        )
        action = parsed.action if parsed else ''
        status = 'ok' if success else 'error'
        duration_ms = int((time.time() - req_start) * 1000) if req_start else 0
        write_call_log(auth.identity_code, domain, action, status, duration_ms=duration_ms)
    except Exception as e:
        logger.debug("Audit log write skipped: %s", e)
        pass  # 日志写入失败不阻断业务


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "28050"))
    uvicorn.run(app, host="0.0.0.0", port=port)
