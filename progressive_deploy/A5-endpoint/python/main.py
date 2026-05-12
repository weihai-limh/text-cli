import os
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

from core.database import init_db
from core.schema_loader import load_schema, reload_schema, get_external_schema, find_backend_url
from core.parser import parse_directive, DirectiveParseError
from core.auth import verify_access_token, increment_token_usage, extract_token_prefix, extract_service_token_prefix
from core.forwarder import forward_request

from api.health import router as health_router
from api.stats import router as stats_router
from api.tokens import router as tokens_router

LOG_LEVEL = os.getenv("LOG_LEVEL", "info").upper()
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))
logger = logging.getLogger(__name__)

ENDPOINT_BASE_URL = os.getenv("ENDPOINT_BASE_URL", "")
ACCESS_TOKEN_REQUIRED = os.getenv("ACCESS_TOKEN_REQUIRED", "true").lower() == "true"
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    load_schema(ENDPOINT_BASE_URL)
    logger.info("Endpoint started. base_url=%s, token_required=%s", ENDPOINT_BASE_URL, ACCESS_TOKEN_REQUIRED)
    yield
    logger.info("Endpoint shutting down.")


app = FastAPI(
    title="text-cli Endpoint",
    description="text-cli 纯转发集成端点",
    version="2.0.0",
    lifespan=lifespan,
)

if ADMIN_API_KEY:
    app.include_router(health_router)
    app.include_router(stats_router)
    app.include_router(tokens_router)
else:
    app.include_router(health_router)


@app.get("/text_cli_schema.json")
async def get_schema():
    return JSONResponse(content=get_external_schema())


@app.post("/cli/text_cli")
async def handle_text_cli(request: Request):
    auth_header = request.headers.get("Authorization", "")
    service_token = request.headers.get("Service-token", "")

    if ACCESS_TOKEN_REQUIRED:
        token_record = verify_access_token(auth_header, required=True)
        if not token_record:
            return JSONResponse(
                status_code=401,
                content={"rst_types": "text", "rst_data": {"text": "ACCESS_DENIED"}},
            )
    else:
        token_record = None

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={"rst_types": "text", "rst_data": {"text": "INVALID_JSON"}},
        )

    prompt = body.get("prompt")
    if not prompt:
        return JSONResponse(
            status_code=400,
            content={"rst_types": "text", "rst_data": {"text": "INVALID_DIRECTIVE_FORMAT: prompt is required"}},
        )

    try:
        parsed = parse_directive(prompt)
    except DirectiveParseError as e:
        return JSONResponse(
            status_code=400,
            content={"rst_types": "text", "rst_data": {"text": f"{e.code}: {e.message}"}},
        )

    backend_url = find_backend_url(parsed.directive_key)
    if not backend_url:
        return JSONResponse(
            status_code=400,
            content={"rst_types": "text", "rst_data": {"text": f"DIRECTIVE_NOT_FOUND: {parsed.directive_key}"}},
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

    content_type = result.headers.get("content-type", "application/json")
    try:
        resp_body = json.loads(result.body)
    except Exception:
        resp_body = result.body.decode("utf-8", errors="replace")

    return JSONResponse(
        status_code=result.status_code,
        content=resp_body if isinstance(resp_body, (dict, list)) else {"rst_types": "text", "rst_data": {"text": resp_body}},
    )


@app.post("/api/schema/reload")
async def api_reload_schema(request: Request):
    if not ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Admin API not configured")
    admin_key = request.headers.get("X-Admin-Key", "")
    if admin_key != ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid admin key")

    count = reload_schema(ENDPOINT_BASE_URL)
    return {"message": "schema reloaded", "directive_count": count}
