"""
text-cli-service — A3 directive service skeleton.
Minimal runnable service: parse → register → authenticate → proxy forward.
Zero external dependencies (no SQLite / MCP / AI).

Start: PORT=28050 SERVICE_TOKEN=your-token python3 main.py
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
    import handlers  # noqa: F401 — triggers auto-registration
    _load_copilot_token()
    _load_schema()
    registered = get_registered_directives()
    logger.info("Registered handlers: %s", registered)
    yield
    logger.info("Shutting down.")


app = FastAPI(
    title="text-cli Directive Service (A3 Skeleton)",
    description="Standard directive service template — parse + auth + registry + proxy. Layer on A5/A6/A7 as needed.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/text_cli_schema.json")
async def get_schema():
    return JSONResponse(content=_schema)


@app.get("/health")
async def health():
    directives = get_registered_directives()
    return {"status": "ok", "directives": directives}


@app.post("/cli/text_cli")
async def handle_directive(request: Request):
    service_token = request.headers.get("Service-token")
    auth = verify_service_token(service_token)
    if not auth.allowed:
        return JSONResponse(
            status_code=403,
            content=error(auth.message),
        )

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content=error("Request body is not valid JSON"),
        )

    prompt = body.get("prompt")
    if not prompt:
        return JSONResponse(
            status_code=400,
            content=error("Missing prompt field"),
        )

    try:
        parsed = parse_directive(prompt)
    except DirectiveParseError as e:
        return JSONResponse(
            status_code=400,
            content=error(f"{e.code}: {e.message}"),
        )

    logger.info(
        "Directive received: %s;%s, params: %s",
        parsed.domain, parsed.action, parsed.params,
    )

    # 1. Local dispatch
    result = dispatch(parsed.domain, parsed.action, parsed.params)
    if result and 'No matching directive' not in result:
        return ok(result)

    # 2. Proxy forward
    proxy_result = proxy_dispatch(parsed.domain, parsed.action,
                                  parsed.params, raw_prompt=prompt)
    if proxy_result is not None:
        return JSONResponse(content=proxy_result)

    # 3. No match
    return ok(result)


@app.api_route("/text-cli-copilot/{rest:path}", methods=["GET", "POST"])
async def copilot_proxy(request: Request, rest: str):
    """Wildcard proxy — forward all requests to copilot:20260."""
    import urllib.request
    import urllib.error

    target = f"http://localhost:20260/{rest}"
    qs = str(request.query_params)
    if qs:
        target += "?" + qs

    body = await request.body() if request.method == "POST" else None

    req = urllib.request.Request(
        target,
        data=body,
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
            content={"rst_types": "text", "rst_data": {"text": f"[proxy] copilot returned {e.code}"},
                      "rst_err": "proxy_error"},
        )
    except Exception as e:
        logger.error("copilot proxy failed: %s", e)
        return JSONResponse(
            status_code=502,
            content={"rst_types": "text", "rst_data": {"text": f"[proxy] {e}"},
                      "rst_err": "proxy_error"},
        )


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "28050"))
    uvicorn.run(app, host="0.0.0.0", port=port)
