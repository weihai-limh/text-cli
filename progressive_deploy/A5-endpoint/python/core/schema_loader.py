import json
import os
import copy
import logging

logger = logging.getLogger(__name__)

SCHEMA_PATH = os.getenv("SCHEMA_PATH", os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "text_cli_schema.json"))

_external_schema: dict[str, dict] = {}


def _load_static_fallback():
    if not os.path.exists(SCHEMA_PATH):
        return {}
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith("_")}


async def load_schema(endpoint_base_url: str | None = None):
    global _external_schema

    backends_raw = os.getenv("A3_BACKENDS", "")
    if backends_raw:
        from core.backend_registry import refresh_backends, build_external_schema
        await refresh_backends()
        _external_schema = build_external_schema(endpoint_base_url)
        logger.info("Schema loaded from %d backends, %d skills available",
                     len(backends_raw.split(",")), len(_external_schema))
    else:
        static = _load_static_fallback()
        _external_schema = copy.deepcopy(static)
        if endpoint_base_url:
            base = endpoint_base_url.rstrip("/")
            target_url = f"{base}/text-cli/cli"
            for key in _external_schema:
                _external_schema[key]["url"] = target_url
        logger.info("Loaded %d directives from static fallback %s", len(_external_schema), SCHEMA_PATH)


async def reload_schema(endpoint_base_url: str | None = None):
    from core.backend_registry import refresh_backends, build_external_schema
    await refresh_backends()
    _external_schema = build_external_schema(endpoint_base_url)
    return len(_external_schema)


def get_external_schema() -> dict[str, dict]:
    return _external_schema


def find_backend_url(directive_key: str) -> str | None:
    from core.backend_registry import find_backend_source
    return find_backend_source(directive_key)


def get_backend_base_url() -> str | None:
    from core.backend_registry import get_backend_base_url as _get_base
    return _get_base()


def _normalize_directive_key(key: str) -> str:
    for prefix in ("指令:", "AI:", "指令：", "AI："):
        if key.startswith(prefix):
            return key[len(prefix):]
    return key
