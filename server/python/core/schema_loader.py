import json
import os
import copy
import logging

logger = logging.getLogger(__name__)

SCHEMA_PATH = os.getenv("SCHEMA_PATH", os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "text_cli_schema.json"))

_internal_schema: dict[str, dict] = {}
_external_schema: dict[str, dict] = {}


def load_schema(endpoint_base_url: str | None = None):
    global _internal_schema, _external_schema

    if not os.path.exists(SCHEMA_PATH):
        logger.warning("Schema file not found at %s, starting with empty schema", SCHEMA_PATH)
        _internal_schema = {}
        _external_schema = {}
        return

    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        _internal_schema = json.load(f)

    logger.info("Loaded %d directives from %s", len(_internal_schema), SCHEMA_PATH)

    _external_schema = copy.deepcopy(_internal_schema)

    if endpoint_base_url:
        base = endpoint_base_url.rstrip("/")
        target_url = f"{base}/cli/text_cli"
        for key in _external_schema:
            _external_schema[key]["url"] = target_url
        logger.info("External schema URLs rewritten to %s", target_url)
    else:
        logger.warning("ENDPOINT_BASE_URL not set, external schema keeps original URLs")


def reload_schema(endpoint_base_url: str | None = None):
    load_schema(endpoint_base_url)
    return len(_internal_schema)


def get_internal_schema() -> dict[str, dict]:
    return _internal_schema


def get_external_schema() -> dict[str, dict]:
    return _external_schema


def find_backend_url(directive_key: str) -> str | None:
    """Find backend URL for a directive key (prefix-agnostic matching)."""
    # Normalize key: strip prefix, keep only domain;action
    normalized = _normalize_directive_key(directive_key)
    for entry in _internal_schema.values():
        entry_normalized = _normalize_directive_key(entry.get("directive", ""))
        if entry_normalized == normalized:
            return entry.get("url")
    return None


def _normalize_directive_key(key: str) -> str:
    """Strip prefix from directive key, e.g. '指令:domain;action' → 'domain;action'"""
    for prefix in ("指令:", "AI:", "指令：", "AI："):
        if key.startswith(prefix):
            return key[len(prefix):]
    return key
