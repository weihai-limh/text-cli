import logging
import os
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

_aggregate_table: dict[str, dict] = {}
_external_schema: dict[str, dict] = {}


def _load_backends() -> list[dict]:
    """Load backend definitions from backends.yaml, falling back to env vars.

    Returns list of {url, token, st_prefix} dicts.
    """
    config_path = Path(__file__).resolve().parent.parent / "backends.yaml"
    if config_path.is_file():
        try:
            import yaml
            with open(config_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if isinstance(data, dict) and isinstance(data.get("backends"), list):
                return [
                    {
                        "url": b["url"].rstrip("/"),
                        "token": b.get("token") or None,
                        "st_prefix": b.get("st_prefix") or None,
                    }
                    for b in data["backends"]
                    if isinstance(b, dict) and b.get("url")
                ]
        except Exception as e:
            logger.warning("Failed to load backends.yaml: %s — falling back to env vars", e)

    # Fallback to comma-separated env vars
    backends_raw = os.getenv("A3_BACKENDS", "")
    if not backends_raw:
        return []

    backends = [b.strip().rstrip("/") for b in backends_raw.split(",") if b.strip()]
    tokens_raw = os.getenv("A3_BACKEND_TOKENS", "")
    tokens = [t.strip() for t in tokens_raw.split(",")] if tokens_raw else []
    st_prefixes_raw = os.getenv("A3_REGISTERED_PREFIXES", "")
    st_prefixes = [p.strip() for p in st_prefixes_raw.split(",")] if st_prefixes_raw else []

    return [
        {
            "url": backends[i],
            "token": tokens[i] if i < len(tokens) else None,
            "st_prefix": st_prefixes[i] if i < len(st_prefixes) else None,
        }
        for i in range(len(backends))
    ]


def _get_backend_urls_from_config() -> list[str]:
    """Get raw backend URLs from config or env for get_backend_base_url."""
    backends = _load_backends()
    return [b["url"] for b in backends] if backends else os.getenv("A3_BACKENDS", "").split(",")


async def refresh_backends():
    global _aggregate_table
    backends = _load_backends()
    if not backends:
        logger.warning("No backends configured — skills aggregation disabled")
        return 0

    new_table = {}
    count = 0

    for backend in backends:
        backend_base = backend["url"]
        token = backend["token"]
        st_prefix = backend["st_prefix"] or ""

        skills = await _fetch_skills(backend_base, token)
        if skills is None:
            logger.warning("Failed to fetch skills from %s", backend_base)
            continue

        for skill in skills:
            skill_id = skill.get("id") or skill.get("directive")
            if not skill_id:
                continue

            normalized = _normalize_skill_id(skill_id)
            if normalized in new_table:
                continue

            new_table[normalized] = {
                "source": backend_base,
                "st_prefix": st_prefix,
                "id": skill.get("id", ""),
                "name": skill.get("name_zh") or skill.get("name", ""),
                "category": skill.get("category", ""),
                "description": skill.get("description_zh") or skill.get("description", ""),
                "directive": skill.get("directive") or skill_id,
                "usage": skill.get("usage_zh") or skill.get("usage", ""),
                "parameters": skill.get("params") or [],
                "prompt_template": skill.get("usage", ""),
                "trigger_keywords": skill.get("trigger_keywords", []),
                "response_type": skill.get("response_type", "text"),
                "response_example": skill.get("response_example"),
            }
            count += 1

        logger.info("Fetched %d skills from %s", len(skills), backend_base)

    _aggregate_table = new_table
    logger.info("Aggregated %d skills from %d backends", count, len(backends))

    from core.auth import update_registered_prefixes
    registered = {entry["st_prefix"] for entry in new_table.values() if entry["st_prefix"]}
    if registered:
        update_registered_prefixes(registered)

    return count


def build_external_schema(endpoint_base_url: str | None = None):
    global _external_schema
    _external_schema = {}

    if not endpoint_base_url:
        return {}

    base = endpoint_base_url.rstrip("/")
    target_url = f"{base}/text-cli/cli"

    for key, entry in _aggregate_table.items():
        _external_schema[key] = {
            "url": target_url,
            "id": entry.get("id", key),
            "name": entry.get("name", ""),
            "category": entry.get("category", ""),
            "description": entry.get("description", ""),
            "directive": entry.get("directive", ""),
            "parameters": entry.get("parameters", []),
            "prompt_template": entry.get("prompt_template", ""),
            "trigger_keywords": entry.get("trigger_keywords", []),
            "response_type": entry.get("response_type", "text"),
            "response_example": entry.get("response_example"),
        }

    return _external_schema


def find_backend_source(directive_key: str) -> str | None:
    normalized = _normalize_skill_id(directive_key)
    entry = _aggregate_table.get(normalized)
    if entry:
        return entry["source"]
    return None


def get_external_schema() -> dict[str, dict]:
    return _external_schema


def get_aggregate_table() -> dict[str, dict]:
    return _aggregate_table


def get_backend_base_url() -> str | None:
    if not _aggregate_table:
        backends = _load_backends()
        if backends:
            return backends[0]["url"]
        return None

    for entry in _aggregate_table.values():
        return entry.get("source")
    return None


def _normalize_skill_id(skill_id: str) -> str:
    for prefix in ("指令:", "AI:", "指令：", "AI："):
        if skill_id.startswith(prefix):
            return skill_id[len(prefix):]
    return skill_id


async def _fetch_skills(backend_base: str, token: str | None) -> list[dict] | None:
    url = f"{backend_base}/text-cli/skills"
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                logger.warning("Skills fetch from %s returned %d", backend_base, resp.status_code)
                return None
            data = resp.json()
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                result = []
                for key, val in data.items():
                    if isinstance(val, dict):
                        val["id"] = f"text-cli;path"
                        val["directive"] = f"text-cli;path,{key}"
                    result.append(val)
                return result
            return []
    except Exception as e:
        logger.warning("Skills fetch from %s failed: %s", backend_base, e)
        return None
