"""
A0 Protocol Consumer — Python SDK.

Zero-dependency text-cli client. One file, no pip install.
Provides call(), discover(), poll(), wait() for AI agents and human scripts.

Usage:
    from call import call, discover, poll, wait

    result = call("AI:tc-math;eval,2+3*4")
    # → DirectiveResult(ok=True, data={"status":"ok","result":14})

    directives = discover()
    # → [{"domain":"tc-math","action":"eval","usage":"tc-math;eval,<expr>",...}, ...]

    status = poll("abc123")
    # → DirectiveResult(is_async=True, data={"state":"running","progress":"50%"})

    final = wait("abc123", on_status=lambda s: print(s.get("state")))
    # → DirectiveResult(ok=True, data={"path":"/media/out.mp4"})
"""

from __future__ import annotations

import json
import logging
import os
import pathlib
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────

_CONF = pathlib.Path(__file__).resolve().parent / "conf.json"
_ENDPOINT: str = ""
_SERVICE_TOKEN: str = ""
_ACCESS_TOKEN: str = ""

# ── Discover cache ────────────────────────────

_discover_cache: dict[str, list[dict]] = {}
_discover_lang: str = "auto"


def _load_config():
    """Load endpoint and tokens from conf.json, fallback to env vars."""
    global _ENDPOINT, _SERVICE_TOKEN, _ACCESS_TOKEN
    if _CONF.exists():
        try:
            data = json.loads(_CONF.read_text(encoding="utf-8"))
            _ENDPOINT = data.get("endpoint", _ENDPOINT)
            _SERVICE_TOKEN = data.get("service_token", _SERVICE_TOKEN)
            _ACCESS_TOKEN = data.get("access_token", _ACCESS_TOKEN)
        except (json.JSONDecodeError, OSError):
            pass
    _ENDPOINT = os.environ.get("TEXT_CLI_ENDPOINT", _ENDPOINT)
    _SERVICE_TOKEN = os.environ.get("TEXT_CLI_SERVICE_TOKEN", _SERVICE_TOKEN)
    _ACCESS_TOKEN = os.environ.get("TEXT_CLI_ACCESS_TOKEN", _ACCESS_TOKEN)
    if not _ENDPOINT:
        _ENDPOINT = "http://127.0.0.1:28050/text-cli/cli"


_load_config()

# ── DirectiveResult ────────────────────────────

@dataclass
class DirectiveResult:
    """Result of a text-cli directive call."""
    ok: bool
    data: Any
    rtype: str = "text"
    err_code: str = ""
    directive: str = ""
    is_async: bool = False

    @property
    def task_id(self) -> str:
        """Return task_id if this is an async result, else empty string."""
        if not self.is_async:
            return ""
        if isinstance(self.data, dict):
            tid = self.data.get("task_id", "")
            if not tid:
                logger.warning("is_async=True but no task_id in data: %s", list(self.data.keys())[:5])
            return tid
        logger.warning("is_async=True but data is not a dict: %s", type(self.data).__name__)
        return ""


# ── HTTP helpers ───────────────────────────────

def _request(prompt: str, timeout: float = 30.0,
             endpoint: str | None = None,
             access_token: str | None = None,
             service_token: str | None = None) -> dict:
    """Send a POST request to the text-cli endpoint and return JSON body.

    Per-call overrides: endpoint, access_token, service_token.
    When omitted (None), fall back to global config / env vars.
    """
    url = endpoint or _ENDPOINT
    body = json.dumps({"prompt": prompt}, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}

    at = access_token if access_token is not None else _ACCESS_TOKEN
    st = service_token if service_token is not None else _SERVICE_TOKEN
    if at:
        headers["Authorization"] = f"Bearer {at}"
    if st:
        headers["Service-token"] = st

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, OSError) as e:
        # Connection refused, DNS failure, timeout, network unreachable
        return {"rst_types": "text",
                "rst_data": {"status": "error", "reason": str(e)},
                "rst_err": "ENDPOINT_UNREACHABLE"}

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"rst_types": "text", "rst_data": {"status": "error", "reason": raw}, "rst_err": "PARSE_ERROR"}


def _parse_envelope(envelope: dict, directive: str = "") -> DirectiveResult:
    """Parse protocol envelope into DirectiveResult."""
    rtype = envelope.get("rst_types", "text")
    rst_data = envelope.get("rst_data", {})
    err_code = envelope.get("rst_err", "")

    ok = err_code == ""
    is_async = (
        isinstance(rst_data, dict)
        and rst_data.get("status") == "pending"
        and "task_id" in rst_data
    )

    return DirectiveResult(
        ok=ok,
        data=rst_data,
        rtype=rtype,
        err_code=err_code,
        directive=directive,
        is_async=is_async,
    )


# ── Public API ─────────────────────────────────

def call(directive: str, timeout: float = 30.0,
         endpoint: str | None = None,
         access_token: str | None = None,
         service_token: str | None = None) -> DirectiveResult:
    """Execute a text-cli directive. Always returns immediately.

    For async tasks, is_async will be True. Use poll() or wait() to track progress.

    Per-call overrides: endpoint, access_token, service_token.
    When omitted, fall back to global config (conf.json / env vars).
    """
    envelope = _request(directive, timeout=timeout,
                        endpoint=endpoint, access_token=access_token,
                        service_token=service_token)
    return _parse_envelope(envelope, directive=directive)


def discover(
    runtime: str | None = None,
    category: str | None = None,
    search: str | None = None,
    lang: str = "auto",
    force_refresh: bool = False,
) -> list[dict]:
    """Fetch available directives from the runtime.

    First call makes one HTTP request (AI:text-cli;query,json).
    Subsequent calls reuse the cached result unless force_refresh=True.
    """
    global _discover_cache, _discover_lang

    # Refresh if forced, lang changed, or cache empty
    cache_key = lang
    if force_refresh:
        _discover_cache.pop(cache_key, None)

    if cache_key not in _discover_cache:
        tail = f",{lang}" if lang != "auto" else ""
        result = call(f"AI:text-cli;query,json{tail}")
        if not result.ok or not isinstance(result.data, dict):
            return []
        raw = result.data
        directives = raw.get("directives", []) if isinstance(raw, dict) else []
        _discover_cache[cache_key] = directives
        _discover_lang = lang

    cached = _discover_cache[cache_key]

    # Client-side filtering
    results = list(cached)
    if runtime:
        results = [d for d in results if d.get("runtime") == runtime]
    if category:
        results = [d for d in results if d.get("_package", {}).get("category") == category
                   or d.get("category") == category]
    if search:
        kw = search.lower()
        results = [d for d in results if (
            kw in d.get("domain", "").lower()
            or kw in d.get("action", "").lower()
            or kw in d.get("usage", "").lower()
            or kw in d.get("description", "").lower()
            or kw in d.get("domain_zh", "").lower()
            or kw in d.get("action_zh", "").lower()
            or kw in d.get("description_zh", "").lower()
            or kw in d.get("package", "").lower()
        )]

    return results


def poll(task_id: str) -> DirectiveResult:
    """Query task status once. Returns immediately.

    While task is pending/running, result.is_async stays True.
    """
    envelope = _request(f"AI:task;status,{task_id}")
    result = _parse_envelope(envelope, directive=f"task;status,{task_id}")

    if not result.ok:
        return result

    task_data = result.data
    if isinstance(task_data, dict):
        state = task_data.get("state", task_data.get("status", ""))
        if state in ("pending", "running"):
            result.is_async = True
        elif state == "done":
            result.is_async = False
            inner = task_data.get("result", {})
            if isinstance(inner, dict):
                result.data = inner
                result.ok = True
        elif state == "error":
            result.is_async = False
            result.ok = False
            result.err_code = "TASK_ERROR"

    return result


def wait(
    task_id: str,
    on_status: Callable[[dict], None] | None = None,
    max_wait: float = 60.0,
    interval: float = 2.0,
) -> DirectiveResult:
    """Wait for task completion with optional progress callbacks.

    Polls with exponential backoff: interval, interval*2, ... up to 30s max.
    Calls on_status(state_dict) after each poll.
    """
    elapsed = 0.0
    current_interval = min(interval, 30.0)

    while elapsed < max_wait:
        result = poll(task_id)

        if on_status and isinstance(result.data, dict):
            on_status(result.data)

        if not result.is_async:
            return result

        time.sleep(current_interval)
        elapsed += current_interval
        current_interval = min(current_interval * 2, 30.0)

    return DirectiveResult(
        ok=False,
        data={"reason": f"Task {task_id} did not complete within {max_wait}s"},
        err_code="TASK_TIMEOUT",
        directive=f"task;wait,{task_id}",
        is_async=False,
    )


def clear_discover_cache():
    """Clear the discover() cache. Use after installing new directive packages."""
    global _discover_cache, _discover_lang
    _discover_cache.clear()
    _discover_lang = "auto"


# ── Batch ──────────────────────────────────────

def call_batch(directives: list[str], timeout: float = 30.0) -> list[DirectiveResult]:
    """Execute multiple directives sequentially. Returns one result per directive."""
    return [call(d, timeout=timeout) for d in directives]
