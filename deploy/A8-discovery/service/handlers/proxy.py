"""
Proxy forwarding handler — forwards matched directives to downstream services (e.g. copilot).
v1.1: async HTTP via httpx.AsyncClient, per-peer credential injection, federation mesh.
"""

import asyncio
import json
import logging
import os
import sqlite3
import threading
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

_PROJECT = Path(os.environ.get("TEXT_CLI_HOME", str(Path.home() / "text-cli")))
PROXY_CONFIG_PATH = str(_PROJECT / "service" / "config" / "proxy_routes.json")

# ── Federation mesh exceptions ─────────────────

class MeshLoopError(Exception):
    """Raised when a loop is detected in multi-hop mesh routing."""


class MeshDepthError(Exception):
    """Raised when max hop depth is exceeded in multi-hop mesh routing."""


# ── Mesh constants ────────────────────────────

MAX_HOP_DEPTH = 5
DEFAULT_TIMEOUT = 30  # seconds
MAX_RETRIES = 2       # exponential backoff: 2^attempt seconds

# ── Peer credentials ──────────────────────
_peer_db_file: str | None = None
_peer_local = threading.local()


def _get_peer_db() -> sqlite3.Connection | None:
    """Thread-local SQLite connection for peer_credentials."""
    if not _peer_db_file:
        return None
    if not hasattr(_peer_local, "conn") or _peer_local.conn is None:
        _peer_local.conn = sqlite3.connect(_peer_db_file)
        _peer_local.conn.row_factory = sqlite3.Row
    return _peer_local.conn


def init_peer_credentials(sqlite_db_file: str):
    """Create peer_credentials table and set DB file path (called via handler_inits)."""
    global _peer_db_file
    _peer_db_file = sqlite_db_file
    db = _get_peer_db()
    if db is None:
        return
    db.execute("""
        CREATE TABLE IF NOT EXISTS peer_credentials (
            peer TEXT PRIMARY KEY,
            service_token TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)
    db.commit()
    logger.info("peer_credentials table initialised")


def get_peer_credentials(peer: str) -> dict | None:
    """Query credentials for a specific peer from the peer_credentials table."""
    db = _get_peer_db()
    if db is None:
        return None
    row = db.execute("SELECT * FROM peer_credentials WHERE peer=?", (peer,)).fetchone()
    if row:
        return dict(row)
    return None


def _resolve_config(path: str) -> str:
    if os.path.exists(path):
        return path
    example_path = path.replace('.json', '.example.json')
    if os.path.exists(example_path):
        logger.info("Using example config: %s", example_path)
        return example_path
    return path

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


def reset_proxy_routes():
    """重置 proxy 路由缓存，使下次 get_proxy_routes() 重新从文件加载。"""
    global _proxy_routes
    _proxy_routes = None


def get_proxy_routes() -> dict:
    global _proxy_routes
    if _proxy_routes is None:
        _proxy_routes = _load_proxy_routes()
    return _proxy_routes


async def proxy_dispatch(domain: str, action: str, params: list[str],
                         raw_prompt: str = "", db_path: dict | None = None) -> dict | None:
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

    # Credential injection: per-peer credentials from peer_credentials table
    peer = route.get("peer")
    if peer and db_path:
        creds = get_peer_credentials(peer)
        if creds:
            body_data["_injected_credentials"] = {peer: creds}
            logger.info("proxy injected credentials for peer %s into %s", peer, lookup)
        else:
            logger.warning("No credentials found for peer %s", peer)
    elif peer and not db_path:
        logger.warning("SQLite not installed, federation mesh unavailable")
    elif not peer and SQLITE_AVAILABLE and db_path:
        # Fallback: no peer specified, inject all keys (legacy behavior)
        all_keys = get_all_keys(db_path)
        if all_keys:
            body_data["_injected_credentials"] = all_keys
            logger.info("proxy injected %d credentials into %s (no peer, legacy)", len(all_keys), lookup)

    timeout = httpx.Timeout(30.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                target_url,
                json=body_data,
                headers={
                    'Authorization': f'Bearer {token}',
                },
            )
            result = resp.json()
            if sensitive:
                result["rst_data"] = {"text": "[redacted]"}
                logger.info("proxy %s -> %s OK (sensitive, masked)", lookup, target_url)
            else:
                logger.info("proxy %s -> %s OK", lookup, target_url)
            return result
    except httpx.HTTPStatusError as e:
        logger.error("proxy %s -> %s HTTP %d", lookup, target_url, e.response.status_code)
        return {"rst_types": "text", "rst_data": {"text": f"[proxy_error] downstream returned {e.response.status_code}"},
                "rst_err": "proxy_error"}
    except httpx.TimeoutException as e:
        logger.error("proxy %s -> %s timeout: %s", lookup, target_url, e)
        return {"rst_types": "text", "rst_data": {"text": f"[proxy_error] timeout: {e}"},
                "rst_err": "proxy_error"}
    except Exception as e:
        logger.error("proxy %s -> %s failed: %s", lookup, target_url, e)
        return {"rst_types": "text", "rst_data": {"text": f"[proxy_error] {e}"},
                "rst_err": "proxy_error"}


# ── Phase 10: Federation mesh multi-hop ───────

async def proxy_with_retry(target_url: str, body_data: dict, token: str,
                           retries: int = MAX_RETRIES,
                           timeout: float = DEFAULT_TIMEOUT) -> dict:
    """POST with exponential backoff retry on timeout.

    Args:
        target_url: Full endpoint URL.
        body_data: JSON-serializable request body.
        token: Bearer token for Authorization header.
        retries: Max retry attempts (default MAX_RETRIES=2).
        timeout: Per-request timeout in seconds (default DEFAULT_TIMEOUT=30).

    Returns:
        Parsed JSON response dict.

    Raises:
        httpx.TimeoutException: All retries exhausted.
        httpx.HTTPStatusError: Non-2xx response (not retried).
    """
    last_exc = None
    for attempt in range(retries + 1):
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
                resp = await client.post(
                    target_url,
                    json=body_data,
                    headers={'Authorization': f'Bearer {token}'},
                )
                resp.raise_for_status()
                return resp.json()
        except httpx.TimeoutException as e:
            last_exc = e
            if attempt < retries:
                wait = 2 ** attempt
                logger.warning("mesh retry %d/%d for %s after %ds", attempt + 1, retries,
                               target_url, wait)
                await asyncio.sleep(wait)
        except httpx.HTTPStatusError:
            raise  # Don't retry HTTP errors
    raise last_exc  # All retries exhausted


async def proxy_dispatch_multi_hop(domain: str, action: str, params: list[str],
                                   raw_prompt: str = "", db_path: dict | None = None,
                                   visited: set = None, depth: int = 0) -> dict | None:
    """Multi-hop mesh proxy: forward through peer chain with loop detection.

    Each proxy_routes.json entry may specify a 'peer' that maps to another
    text-cli node. This function resolves the peer chain using visited-set
    and depth-limit guards.

    Args:
        domain, action, params: Parsed directive components.
        raw_prompt: Original AI: prompt for forwarding.
        db_path: SQLite config dict for credential lookup.
        visited: Accumulated peer set for loop detection (caller leaves None).
        depth: Current hop depth (caller leaves 0).

    Returns:
        Response dict from final node, or None if no route.

    Raises:
        MeshLoopError: Circular peer chain detected.
        MeshDepthError: MAX_HOP_DEPTH exceeded.
    """
    if visited is None:
        visited = set()
    if depth > MAX_HOP_DEPTH:
        raise MeshDepthError(
            f"Max hop depth {MAX_HOP_DEPTH} exceeded at {domain};{action}")

    routes = get_proxy_routes()
    lookup = f"{domain};{action}"
    route = routes.get(lookup)
    if not route:
        return None

    peer = route.get("peer")
    if peer and peer in visited:
        raise MeshLoopError(
            f"Loop detected: {peer} already visited (chain: {' → '.join(sorted(visited))})")
    if peer:
        visited.add(peer)

    target_url = route.get('url', '')
    token = route.get('token', '')
    sensitive = route.get('sensitive', False)
    if not target_url:
        return None

    body_data = {"prompt": raw_prompt}

    # Per-peer credential injection
    if peer and db_path:
        creds = get_peer_credentials(peer)
        if creds:
            body_data["_injected_credentials"] = {peer: creds}
        else:
            logger.warning("No credentials for peer %s in multi-hop chain", peer)
    elif not db_path:
        logger.warning("SQLite not installed, federation mesh unavailable")

    # Forward with retry
    try:
        result = await proxy_with_retry(target_url, body_data, token)
        if sensitive:
            result.setdefault("rst_data", {})["text"] = "[redacted]"
            logger.info("mesh %d-hop %s -> %s OK (sensitive)", depth, lookup, target_url)
        else:
            logger.info("mesh %d-hop %s -> %s OK", depth, lookup, target_url)

        # If result contains a peer redirect, recurse
        next_peer = result.get("_mesh_redirect")
        if next_peer:
            next_domain, _, next_action = next_peer.partition(";")
            return await proxy_dispatch_multi_hop(
                next_domain, next_action, params,
                raw_prompt=raw_prompt, db_path=db_path,
                visited=visited, depth=depth + 1)

        return result
    except (MeshLoopError, MeshDepthError):
        raise
    except httpx.TimeoutException as e:
        logger.error("mesh %d-hop %s -> %s timeout", depth, lookup, target_url)
        return {"rst_types": "text", "rst_data": {"text": f"[mesh_timeout] {e}"},
                "rst_err": "ERR_ROUTING"}
    except httpx.HTTPStatusError as e:
        logger.error("mesh %d-hop %s -> %s HTTP %d", depth, lookup, target_url,
                     e.response.status_code)
        return {"rst_types": "text",
                "rst_data": {"text": f"[mesh_error] downstream returned {e.response.status_code}"},
                "rst_err": "ERR_ROUTING"}
    except Exception as e:
        logger.error("mesh %d-hop %s -> %s failed: %s", depth, lookup, target_url, e)
        return {"rst_types": "text", "rst_data": {"text": f"[mesh_error] {e}"},
                "rst_err": "ERR_ROUTING"}
