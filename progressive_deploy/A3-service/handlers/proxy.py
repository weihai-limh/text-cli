"""
Proxy forwarding handler — forwards matched directives to downstream services (e.g. copilot).
v1.1: supports credential injection from SQLite into forwarded requests.
"""

import json
import logging
import os
import urllib.request
import urllib.error
from pathlib import Path

logger = logging.getLogger(__name__)

_PROJECT = Path(os.environ.get("TEXT_CLI_HOME", str(Path.home() / "text-cli")))
PROXY_CONFIG_PATH = str(_PROJECT / "service" / "config" / "proxy_routes.json")

# Try loading SQLite for credential injection
try:
    from text_cli_modules.key.key_registry import get_all_keys
    SQLITE_AVAILABLE = True
except ImportError:
    SQLITE_AVAILABLE = False
    def get_all_keys(*args, **kwargs):
        return {}


def _load_proxy_routes() -> dict[str, dict]:
    try:
        with open(PROXY_CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


_proxy_routes = None


def get_proxy_routes() -> dict:
    global _proxy_routes
    if _proxy_routes is None:
        _proxy_routes = _load_proxy_routes()
    return _proxy_routes


def proxy_dispatch(domain: str, action: str, params: list[str],
                   raw_prompt: str = "", db_path: dict = None) -> dict | None:
    """Check proxy routes, forward on match (with credential injection). Returns None if no match."""
    routes = get_proxy_routes()
    lookup = f"{domain};{action}"

    route = routes.get(lookup)
    if not route:
        return None

    target_url = route.get('url', '')
    token = route.get('token', '')
    sensitive = route.get('sensitive', False)

    if not target_url:
        return None

    # Build request body
    body_data = {"prompt": raw_prompt}

    # Credential injection: attach all available keys from SQLite
    if SQLITE_AVAILABLE and db_path:
        all_keys = get_all_keys(db_path)
        if all_keys:
            body_data["_injected_credentials"] = all_keys
            logger.info("proxy injected %d credentials into %s", len(all_keys), lookup)

    body = json.dumps(body_data, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(
        target_url,
        data=body,
        headers={
            'Content-Type': 'application/json; charset=utf-8',
            'Authorization': f'Bearer {token}',
        },
        method='POST',
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            if sensitive:
                logger.info("proxy %s -> %s OK (sensitive)", lookup, target_url)
            else:
                logger.info("proxy %s -> %s OK", lookup, target_url)
            return result
    except urllib.error.HTTPError as e:
        logger.error("proxy %s -> %s HTTP %d", lookup, target_url, e.code)
        return {"rst_types": "text", "rst_data": {"text": f"[proxy_error] downstream returned {e.code}"},
                "rst_err": "proxy_error"}
    except Exception as e:
        logger.error("proxy %s -> %s failed: %s", lookup, target_url, e)
        return {"rst_types": "text", "rst_data": {"text": f"[proxy_error] {e}"},
                "rst_err": "proxy_error"}
