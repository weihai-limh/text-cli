import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from core.parser import parse_directive, DirectiveParseError
from core.auth import verify_service_token
from core.registry import dispatch, get_registered_directives
from core.response import ok, error

LOG_LEVEL = os.getenv("LOG_LEVEL", "info").upper()
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))
logger = logging.getLogger(__name__)

SCHEMA_PATH = os.getenv(
    "SCHEMA_PATH",
    str(project_root / "config" / "text_cli_schema.json"),
)

_schema: dict[str, dict] = {}


def _load_schema():
    global _schema
    if not os.path.exists(SCHEMA_PATH):
        logger.warning("Schema not found: %s", SCHEMA_PATH)
        _schema = {}
        return
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        _schema = json.load(f)
    logger.info("Loaded %d directives from %s", len(_schema), SCHEMA_PATH)


@asynccontextmanager
async def lifespan(app: FastAPI):
    import handlers  # noqa: F401 — triggers auto-registration
    _load_schema()
    registered = get_registered_directives()
    logger.info("Registered handlers: %s", registered)
    yield
    logger.info("Shutting down.")


app = FastAPI(
    title="text-cli 示例指令服务",
    description="text-cli 标准指令服务模板，可被 Service_endpoint 集成",
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
            content=error("请求体不是有效 JSON"),
        )

    prompt = body.get("prompt")
    if not prompt:
        return JSONResponse(
            status_code=400,
            content=error("缺少 prompt 字段"),
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

    result = dispatch(parsed.domain, parsed.action, parsed.params)

    return ok(result)


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
