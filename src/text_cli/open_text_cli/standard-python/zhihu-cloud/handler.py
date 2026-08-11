"""zhihu-cloud handler — Zhihu Open Platform search API wrapper.

Two directives: search (in-site zhihu_search) and global-search (global_search).
Credentials from A6 key_registry (zhihu_api_secret).
"""

import json
import re
import time
import logging
from urllib.parse import quote, unquote

import requests

from core.registry import directive

logger = logging.getLogger(__name__)

ZHIHU_SEARCH_URL = "https://developer.zhihu.com/api/v1/content/zhihu_search"
ZHIHU_GLOBAL_URL = "https://developer.zhihu.com/api/v1/content/global_search"
MAX_SEARCH = 10
MAX_GLOBAL = 20
TIMEOUT = 15

_access_secret: str | None = None
_db_path: dict = {}

_UTM_RE = re.compile(r'[?&]utm_[^&]*')

def _clean_url(url: str) -> str:
    """Remove utm tracking parameters from URL."""
    cleaned = _UTM_RE.sub('', url)
    return cleaned.rstrip('?')

_SENTENCE_BREAK_RE = re.compile(r'[。.！!？?\n]')

def _truncate_snippet(text: str, max_len: int = 300) -> str:
    """Truncate text to max_len, breaking at sentence boundary when possible."""
    if len(text) <= max_len:
        return text
    truncated = text[:max_len]
    best = -1
    for m in _SENTENCE_BREAK_RE.finditer(truncated):
        pos = m.end()
        if pos > max_len * 0.5:
            best = pos
    if best > 0:
        return truncated[:best]
    return truncated

def _reduce_item(item: dict) -> dict:
    """Reduce API item to 6 core fields for AI consumption."""
    content_type = (item.get("ContentType") or "").lower()
    authority = item.get("AuthorityLevel", "")
    voteup = item.get("VoteUpCount", 0)
    if not isinstance(voteup, int):
        voteup = int(voteup) if voteup else 0

    return {
        "title": item.get("Title", ""),
        "url": _clean_url(item.get("Url", "")),
        "snippet": _truncate_snippet(item.get("ContentText", "")),
        "content_type": content_type,
        "authority_level": authority,
        "voteup_count": voteup,
    }

def init_zhihu_cloud_handler(db_path: str):
    """Load zhihu_api_secret from key_registry."""
    global _access_secret
    _db_path["config"] = db_path
    try:
        from text_cli_modules.key.key_registry import get as key_get
        creds = key_get(db_path, "zhihu")
        if creds:
            if isinstance(creds, str):
                _access_secret = creds
            elif isinstance(creds, (list, tuple)):
                _access_secret = creds[0][0] if isinstance(creds[0], (list, tuple)) else creds[0]
            logger.info("zhihu-cloud api_secret loaded")
        else:
            logger.warning("zhihu-cloud: zhihu key not configured in key_registry")
    except ImportError:
        logger.warning("zhihu-cloud: key_registry module not available")

def _request(endpoint: str, query: str, count: int, max_count: int,
             extra_params: dict | None = None) -> dict:
    """Send authenticated GET request to Zhihu Open Platform, return Data dict."""
    if not _access_secret:
        raise RuntimeError("zhihu key not configured in key_registry")

    params: dict = {"Query": query, "Count": str(min(count, max_count))}
    if extra_params:
        params.update(extra_params)

    headers = {
        "Authorization": f"Bearer {_access_secret}",
        "X-Request-Timestamp": str(int(time.time())),
        "Content-Type": "application/json",
    }

    resp = requests.get(endpoint, params=params, headers=headers, timeout=TIMEOUT)
    resp.raise_for_status()
    body = resp.json()
    code = body.get("Code")
    if code != 0:
        msg = body.get("Message", "")
        raise RuntimeError(f"zhihu API error Code={code}: {msg}")
    return body.get("Data", {}) or {}

_ERROR_MAP = {
    10001: "zhihu API parameter error",
    20001: "zhihu API authentication failed",
    30001: "zhihu API rate limit exceeded",
    90001: "zhihu API internal error",
}

def _map_error(code: int) -> str:
    return _ERROR_MAP.get(code, f"zhihu API unknown error (Code={code})")

@directive("zhihu-cloud", "search",
            domain_alias="知乎搜索", action_aliases={"search": "站内搜索"})
def zhihu_cloud_search(params: list[str]) -> dict:
    """zhihu-cloud;search,<query>[,<count>]"""
    if not params:
        return {
            "status": "error",
            "reason": "Usage: zhihu-cloud;search,<query>[,<count>]"
        }

    query = params[0].strip()
    if not query:
        return {
            "status": "error",
            "reason": "query must not be empty"
        }

    count_requested = 10
    if len(params) >= 2:
        try:
            count_requested = int(params[1])
        except ValueError:
            return {
                "status": "error",
                "reason": "count must be an integer"
            }

    try:
        data = _request(ZHIHU_SEARCH_URL, query, count_requested, MAX_SEARCH)
    except RuntimeError as e:
        return {"status": "error", "reason": str(e)}
    except requests.RequestException as e:
        return {"status": "error", "reason": f"zhihu API not reachable: {e}"}

    items = data.get("Items") or []
    sources = [_reduce_item(it) for it in items]
    return {
        "status": "ok",
        "source": "zhihu",
        "query": query,
        "sources": sources,
        "count": len(sources),
        "count_requested": count_requested,
    }

@directive("zhihu-cloud", "global-search",
            domain_alias="知乎搜索", action_aliases={"global-search": "全网搜索"})
def zhihu_cloud_global_search(params: list[str]) -> dict:
    """zhihu-cloud;global-search,<query>[,<count>[,<JSON>]]"""
    if not params:
        return {
            "status": "error",
            "reason": "Usage: zhihu-cloud;global-search,<query>[,<count>[,<JSON>]]"
        }

    query = params[0].strip()
    if not query:
        return {
            "status": "error",
            "reason": "query must not be empty"
        }

    count_requested = 10
    idx = 1
    if len(params) >= 2:
        try:
            count_requested = int(params[1])
        except ValueError:
            pass  # count not provided, treat as JSON string
        else:
            idx = 2

    extra: dict = {}
    search_db = "all"
    if len(params) >= idx + 1:
        try:
            extra_raw = json.loads(",".join(params[idx:]))
            if isinstance(extra_raw, dict):
                if "filter" in extra_raw:
                    extra["Filter"] = extra_raw["filter"]
                if "search_db" in extra_raw and extra_raw["search_db"] in ("all", "realtime", "static"):
                    search_db = extra_raw["search_db"]
                    extra["SearchDB"] = search_db
        except (json.JSONDecodeError, ValueError):
            return {
                "status": "error",
                "reason": "JSON parameter parse failed"
            }

    try:
        data = _request(ZHIHU_GLOBAL_URL, query, count_requested, MAX_GLOBAL, extra)
    except RuntimeError as e:
        return {"status": "error", "reason": str(e)}
    except requests.RequestException as e:
        return {"status": "error", "reason": f"zhihu API not reachable: {e}"}

    items = data.get("Items") or []
    sources = [_reduce_item(it) for it in items]
    return {
        "status": "ok",
        "source": "zhihu",
        "query": query,
        "search_db": search_db,
        "sources": sources,
        "count": len(sources),
        "count_requested": count_requested,
    }
