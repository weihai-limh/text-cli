import json
import logging
import os
from contextlib import asynccontextmanager

from api.health import router as health_router
from api.stats import router as stats_router
from api.tokens import router as tokens_router
from core.auth import (
    extract_service_token_prefix,
    increment_token_usage,
    is_st_prefix_blocked,
    is_st_prefix_registered,
    verify_access_token,
)
from core.database import init_db
from core.forwarder import forward_request, forward_skill_request
from core.ip_guard import is_ip_blocked
from core.response import err
from core.parser import DirectiveParseError, parse_directive
from core.rate_limiter import check_rate_limit
from core.schema_loader import (
    find_backend_url,
    get_backend_base_url,
    get_external_schema,
    load_schema,
    reload_schema,
)
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

LOG_LEVEL = os.getenv("LOG_LEVEL", "info").upper()
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))
logger = logging.getLogger(__name__)

ENDPOINT_BASE_URL = os.getenv("ENDPOINT_BASE_URL", "http://localhost:29050")
ACCESS_TOKEN_REQUIRED = os.getenv("ACCESS_TOKEN_REQUIRED", "true").lower() == "true"
ENABLE_PUBLIC_CLI = os.getenv("ENABLE_PUBLIC_CLI", "false").lower() == "true"
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    await load_schema(ENDPOINT_BASE_URL)
    logger.info("Endpoint started. base_url=%s, token_required=%s", ENDPOINT_BASE_URL, ACCESS_TOKEN_REQUIRED)
    yield
    logger.info("Endpoint shutting down.")


app = FastAPI(
    title="text-cli Endpoint",
    description="text-cli 纯转发集成端点",
    version="0.1.1",
    lifespan=lifespan,
)

if ADMIN_API_KEY:
    app.include_router(health_router)
    app.include_router(stats_router)
    app.include_router(tokens_router)
else:
    app.include_router(health_router)


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    client_ip = (
        request.client.host
        if request.client
        else request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    )

    if is_ip_blocked(client_ip):
        return JSONResponse(
            status_code=403,
            content=err("IP_BLOCKED", "ACCESS_DENIED"),
        )

    if request.url.path == "/text-cli/cli" and request.method == "POST":
        service_token = request.headers.get("Service-token", "")
        if service_token:
            prefix = extract_service_token_prefix(service_token)
            if is_st_prefix_blocked(prefix):
                return JSONResponse(
                    status_code=403,
                    content=err("TOKEN_PREFIX_BLOCKED", "ACCESS_DENIED"),
                )
            if not is_st_prefix_registered(prefix):
                return JSONResponse(
                    status_code=403,
                    content=err("TOKEN_PREFIX_UNKNOWN", "ACCESS_DENIED"),
                )

    path = request.url.path
    method = request.method
    if path == "/text-cli/cli" and not check_rate_limit(is_get=(method == "GET")):
            return JSONResponse(
                status_code=429,
                content=err("RATE_LIMIT_EXCEEDED", "ACCESS_DENIED"),
            )

    response = await call_next(request)
    return response


@app.get("/text_cli_schema.json")
async def get_schema():
    return JSONResponse(content=get_external_schema())


@app.post("/text-cli/cli")
async def handle_text_cli(request: Request):
    auth_header = request.headers.get("Authorization", "")
    service_token = request.headers.get("Service-token", "")

    if ACCESS_TOKEN_REQUIRED:
        token_record = verify_access_token(auth_header, required=True)
        if not token_record:
            return JSONResponse(
                status_code=401,
                content=err("ACCESS_DENIED", "ACCESS_DENIED"),
            )
    else:
        token_record = None

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content=err("INVALID_JSON", "INVALID_PARAMS"),
        )

    prompt = body.get("prompt")
    if not prompt:
        return JSONResponse(
            status_code=400,
            content=err("INVALID_DIRECTIVE_FORMAT: prompt is required", "INVALID_PARAMS"),
        )

    try:
        parsed = parse_directive(prompt)
    except DirectiveParseError as e:
        return JSONResponse(
            status_code=400,
            content=err(f"{e.code}: {e.message}", "INVALID_PARAMS"),
        )

    backend_url = find_backend_url(parsed.directive_key)
    if not backend_url:
        return JSONResponse(
            status_code=400,
            content=err(f"DIRECTIVE_NOT_FOUND: {parsed.directive_key}", "ERR_NOT_FOUND"),
        )

    access_token = None
    if auth_header.startswith("Bearer "):
        access_token = auth_header[7:].strip()

    result = await forward_request(
        parsed=parsed,
        backend_url=backend_url,
        prompt=prompt,
        access_token=access_token,
        service_token=service_token,
    )

    if token_record:
        increment_token_usage(token_record["token_prefix"])

    _content_type = result.headers.get("content-type", "application/json")
    try:
        resp_body = json.loads(result.body)
    except Exception:
        resp_body = result.body.decode("utf-8", errors="replace")

    return JSONResponse(
        status_code=result.status_code,
        content=resp_body if isinstance(resp_body, (dict, list)) else err(resp_body, "ERR_ROUTING"),
    )


@app.post("/api/schema/reload")
async def api_reload_schema(request: Request):
    if not ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Admin API not configured")
    admin_key = request.headers.get("X-Admin-Key", "")
    if admin_key != ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid admin key")

    count = await reload_schema(ENDPOINT_BASE_URL)
    return {"message": "schema reloaded", "directive_count": count}


@app.get("/text-cli/cli")
async def handle_public_cli(request: Request):
    if not ENABLE_PUBLIC_CLI:
        return JSONResponse(
            status_code=404,
            content=err("PUBLIC_CLI_DISABLED", "ERR_NOT_FOUND"),
        )

    skill_id = request.query_params.get("skill_id")
    if not skill_id:
        return JSONResponse(
            status_code=400,
            content=err("INVALID_PARAMS: skill_id is required", "INVALID_PARAMS"),
        )

    backend_base = get_backend_base_url()
    if not backend_base:
        return JSONResponse(
            status_code=502,
            content=err("BACKEND_UNAVAILABLE", "ERR_ROUTING"),
        )

    body = {k: v for k, v in request.query_params.items() if k != "skill_id"}
    service_token = request.headers.get("Service-token", "") or None

    status_code, resp_text = await forward_skill_request(backend_base, skill_id, body, service_token)

    try:
        resp_body = json.loads(resp_text)
    except Exception:
        resp_body = resp_text

    return JSONResponse(
        status_code=status_code,
        content=resp_body if isinstance(resp_body, (dict, list)) else err(resp_body, "ERR_ROUTING"),
    )
