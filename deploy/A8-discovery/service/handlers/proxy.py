"""
Proxy forwarding handler — forwards matched directives to downstream services (e.g. copilot).
v1.2: async HTTP via httpx.AsyncClient, credential injection via external injector, federation mesh.

Credential injection is handled by MeshCredentialInjector (A6 layer). A3 proxy.py is a pure
forwarding pipe — it does NOT import or depend on SQLite, peer_credentials, or credential logic.
"""

import asyncio
import json
import logging
import os
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

# Mesh multi-hop config cache — lazy-loaded once per process lifetime
_mesh_config_cache: tuple | None = None


def _get_mesh_config() -> tuple:
    """Lazy load mesh multi-hop config with graceful degradation."""
    global _mesh_config_cache
    if _mesh_config_cache is not None:
        return _mesh_config_cache
    try:
        from core.config import load_config
        config = load_config()
        mesh = config.get("mesh", {})
        _mesh_config_cache = (
            mesh.get("multi_hop_enabled", False),
            mesh.get("multi_hop_max_depth", 3),
        )
    except Exception:
        _mesh_config_cache = (False, 3)
    return _mesh_config_cache


def _resolve_config(path: str) -> str:
    if os.path.exists(path):
        return path
    example_path = path.replace('.json', '.example.json')
    if os.path.exists(example_path):
        logger.info("Using example config: %s", example_path)
        return example_path
    return path


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
                         raw_prompt: str = "", credential_injector=None) -> dict | None:
    """Check proxy routes, forward on match. Returns None if no match.

    credential_injector: optional MeshCredentialInjector instance (A6 layer).
        When provided, injector.inject(body, peer) is called before forwarding.
        A3 standalone deployments pass None (pure forwarding, no credentials).
    """
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

    # Credential injection — delegated to external injector (A6 layer)
    peer = route.get("peer")
    if credential_injector is not None:
        try:
            body_data = credential_injector.inject(body_data, peer)
        except Exception as e:
            logger.error("mesh credential injector failed for peer %s: %s", peer, e)
            return {"rst_types": "text",
                    "rst_data": {"status": "error",
                                 "reason": f"mesh_credential_unavailable: {e}"},
                    "rst_err": "ERR_ROUTING"}

    timeout = httpx.Timeout(30.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            headers = {}
            if token:
                headers['Authorization'] = f'Bearer {token}'
            resp = await client.post(
                target_url,
                json=body_data,
                headers=headers,
            )
            result = resp.json()
            if sensitive:
                result["rst_data"] = {"status": "redacted", "reason": "[redacted]"}
                logger.info("proxy %s -> %s OK (sensitive, masked)", lookup, target_url)
            else:
                logger.info("proxy %s -> %s OK", lookup, target_url)

            # Multi-hop follow — if enabled and result signals a redirect
            multi_hop_enabled, _ = _get_mesh_config()
            next_peer = result.get("_mesh_redirect") if multi_hop_enabled else None
            if next_peer:
                next_domain, _, next_action = next_peer.partition(";")
                return await proxy_dispatch_multi_hop(
                    next_domain, next_action, params,
                    raw_prompt=raw_prompt, credential_injector=credential_injector,
                    visited={peer} if peer else set(), depth=1)

            return result
    except httpx.HTTPStatusError as e:
        logger.error("proxy %s -> %s HTTP %d", lookup, target_url, e.response.status_code)
        return {"rst_types": "text", "rst_data": {"status": "error", "reason": f"[proxy_error] downstream returned {e.response.status_code}"},
                "rst_err": "proxy_error"}
    except httpx.TimeoutException as e:
        logger.error("proxy %s -> %s timeout: %s", lookup, target_url, e)
        return {"rst_types": "text", "rst_data": {"status": "error", "reason": f"[proxy_error] timeout: {e}"},
                "rst_err": "proxy_error"}
    except Exception as e:
        logger.error("proxy %s -> %s failed: %s", lookup, target_url, e)
        return {"rst_types": "text", "rst_data": {"status": "error", "reason": f"[proxy_error] {e}"},
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
                headers = {}
                if token:
                    headers['Authorization'] = f'Bearer {token}'
                resp = await client.post(
                    target_url,
                    json=body_data,
                    headers=headers,
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
                                   raw_prompt: str = "", credential_injector=None,
                                   visited: set = None, depth: int = 0) -> dict | None:
    """Multi-hop mesh proxy: forward through peer chain with loop detection.

    Each proxy_routes.json entry may specify a 'peer' that maps to another
    text-cli node. This function resolves the peer chain using visited-set
    and depth-limit guards.

    Args:
        domain, action, params: Parsed directive components.
        raw_prompt: Original AI: prompt for forwarding.
        credential_injector: optional MeshCredentialInjector instance (A6 layer).
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
    _, depth_cfg = _get_mesh_config()
    effective_max = min(depth_cfg, MAX_HOP_DEPTH)
    if depth > effective_max:
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

    # Credential injection — delegated to external injector (A6 layer)
    if credential_injector is not None:
        try:
            body_data = credential_injector.inject(body_data, peer)
        except Exception as e:
            logger.error("mesh credential injector failed for peer %s (hop %d): %s",
                         peer, depth, e)
            return {"rst_types": "text",
                    "rst_data": {"status": "error",
                                 "reason": f"mesh_credential_unavailable: {e}"},
                    "rst_err": "ERR_ROUTING"}

    # Forward with retry
    try:
        result = await proxy_with_retry(target_url, body_data, token)
        if sensitive:
            result["rst_data"] = {"status": "redacted", "reason": "[redacted]"}
            logger.info("mesh %d-hop %s -> %s OK (sensitive)", depth, lookup, target_url)
        else:
            logger.info("mesh %d-hop %s -> %s OK", depth, lookup, target_url)

        # If result contains a peer redirect, recurse
        next_peer = result.get("_mesh_redirect")
        if next_peer:
            next_domain, _, next_action = next_peer.partition(";")
            return await proxy_dispatch_multi_hop(
                next_domain, next_action, params,
                raw_prompt=raw_prompt, credential_injector=credential_injector,
                visited=visited, depth=depth + 1)

        return result
    except (MeshLoopError, MeshDepthError):
        raise
    except httpx.TimeoutException as e:
        logger.error("mesh %d-hop %s -> %s timeout", depth, lookup, target_url)
        return {"rst_types": "text", "rst_data": {"status": "error", "reason": f"[mesh_timeout] {e}"},
                "rst_err": "ERR_ROUTING"}
    except httpx.HTTPStatusError as e:
        logger.error("mesh %d-hop %s -> %s HTTP %d", depth, lookup, target_url,
                     e.response.status_code)
        return {"rst_types": "text",
                "rst_data": {"status": "error", "reason": f"[mesh_error] downstream returned {e.response.status_code}"},
                "rst_err": "ERR_ROUTING"}
    except Exception as e:
        logger.error("mesh %d-hop %s -> %s failed: %s", depth, lookup, target_url, e)
        return {"rst_types": "text", "rst_data": {"status": "error", "reason": f"[mesh_error] {e}"},
                "rst_err": "ERR_ROUTING"}
