"""
bd-cloud handler — Baidu Cloud API instruction package.

P1 directives: ocr, baike, search, video-notes (async), video-notes-result (internal)

Credentials from A6 SQLite key_registry (bd-ocr + bd-qianfan).
Quota: integrated with quota-manage.

Author: Tide 🌊 — 2026-05-17
"""

import os
import base64
import time
import logging
from pathlib import Path

import requests

from core.registry import directive

logger = logging.getLogger(__name__)

DB_PATH: dict = {}

def _get_ocr_credentials() -> tuple[str, str]:
    """Get OCR API Key + Secret Key from key_registry."""
    if not DB_PATH:
        init_bd_cloud_handler()
    try:
        from text_cli_modules.key.key_registry import get
        keys = get(DB_PATH, "bd-ocr")
        if isinstance(keys, list) and len(keys) >= 2:
            return keys[0], keys[1]
        raise RuntimeError("bd-ocr key not properly configured (need API Key + Secret Key)")
    except ImportError:
        raise RuntimeError("key_registry not available. Register bd-ocr key first.")
    except Exception as e:
        raise RuntimeError(f"Failed to retrieve bd-ocr credentials: {e}")

def _get_qianfan_bearer() -> str:
    """Get Qianfan Bearer token from key_registry (with env var fallback)."""
    if not DB_PATH:
        init_bd_cloud_handler()
    try:
        from text_cli_modules.key.key_registry import get
        token = get(DB_PATH, "bd-qianfan")
        if isinstance(token, str) and token:
            return token
        if isinstance(token, list) and token:
            return token[0]
    except Exception:
        pass
    token = os.environ.get("BAIDU_QIANFAN_BEARER", "")
    if token:
        return token
    raise RuntimeError("bd-qianfan key not configured. Register via key;register or set BAIDU_QIANFAN_BEARER")

_ocr_token: str | None = None
_ocr_token_expiry: float = 0

OCR_TOKEN_TTL = 3600 * 24  # 24h (Baidu tokens typically last 30 days, but refresh daily)

def _get_ocr_access_token() -> str:
    """Get or refresh Baidu OCR OAuth access token."""
    global _ocr_token, _ocr_token_expiry
    if _ocr_token and time.time() < _ocr_token_expiry:
        return _ocr_token

    api_key, secret_key = _get_ocr_credentials()
    url = "https://aip.baidubce.com/oauth/2.0/token"
    params = {
        "grant_type": "client_credentials",
        "client_id": api_key,
        "client_secret": secret_key,
    }
    resp = requests.post(url, params=params, timeout=10)
    data = resp.json()
    token = data.get("access_token")
    if not token:
        raise RuntimeError(f"Failed to get OCR access token: {data.get('error_description', resp.text)}")
    _ocr_token = token
    _ocr_token_expiry = time.time() + OCR_TOKEN_TTL
    logger.info("bd-cloud OCR token refreshed")
    return token

def _normalize_image(image_input: str) -> str:
    """URL or local path → base64 (Baidu OCR uses base64)."""
    if image_input.startswith("http"):
        resp = requests.get(image_input, timeout=30)
        resp.raise_for_status()
        return base64.b64encode(resp.content).decode("utf-8")
    else:
        path = Path(image_input)
        if not path.exists():
            raise FileNotFoundError(f"Image file not found: {image_input}")
        return base64.b64encode(path.read_bytes()).decode("utf-8")

def _check_quota(target: str, amount: int = 1) -> dict | None:
    try:
        from handlers.quota_handler import check_and_update
        result = check_and_update(target, amount)
        if result.get("status") == "stop":
            return result
        return None
    except ImportError:
        return None
    except Exception as e:
        logger.warning("quota check failed for %s: %s", target, e)
        return None

@directive("bd-cloud", "ocr", domain_alias="百度云", action_aliases={"ocr": "文字识别"})
def bd_cloud_ocr(params: list[str]) -> dict:
    """bd-cloud;ocr,<image_url_or_path>"""
    if not params:
        return {
            "status": "error",
            "reason": "Usage: bd-cloud;ocr,<image_URL_or_local_path>"
        }

    image_input = params[0]
    blocked = _check_quota("bd-cloud-ocr")
    if blocked:
        return blocked

    try:
        image_b64 = _normalize_image(image_input)
        token = _get_ocr_access_token()
        url = f"https://aip.baidubce.com/rest/2.0/ocr/v1/general_basic?access_token={token}"
        payload = f"image={requests.utils.quote(image_b64)}&language_type=CHN_ENG"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }
        resp = requests.post(url, headers=headers, data=payload.encode("utf-8"), timeout=30)
        data = resp.json()

        words = [item["words"] for item in data.get("words_result", [])]
        return {
            "status": "ok",
            "text": words, "count": len(words),
        }
    except FileNotFoundError as e:
        return {"status": "error", "reason": str(e)}
    except RuntimeError as e:
        return {"status": "error", "reason": str(e)}
    except Exception as e:
        logger.exception("bd-cloud OCR failed")
        return {"status": "error", "reason": f"OCR failed: {e}"}

@directive("bd-cloud", "baike", domain_alias="百度云", action_aliases={"baike": "百科"})
def bd_cloud_baike(params: list[str]) -> dict:
    """bd-cloud;baike,<keyword>"""
    if not params:
        return {
            "status": "error",
            "reason": "Usage: bd-cloud;baike,<keyword>"
        }

    keyword = params[0]
    blocked = _check_quota("bd-cloud-baike")
    if blocked:
        return blocked

    try:
        bearer = _get_qianfan_bearer()
        url = f"https://appbuilder.baidu.com/v2/baike/lemma/get_content?search_type=lemmaTitle&search_key={requests.utils.quote(keyword)}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {bearer}",
        }
        resp = requests.get(url, headers=headers, timeout=15)
        data = resp.json()
        result = data.get("result", {})

        return {
            "status": "ok",
            "title": result.get("lemma_title", ""),
            "summary": result.get("summary", ""),
            "lemma_id": result.get("lemma_id", ""),
        }
    except RuntimeError as e:
        return {"status": "error", "reason": str(e)}
    except Exception as e:
        logger.exception("bd-cloud baike failed")
        return {"status": "error", "reason": f"Baike failed: {e}"}

@directive("bd-cloud", "search", domain_alias="百度云", action_aliases={"search": "搜索"})
def bd_cloud_search(params: list[str]) -> dict:
    """bd-cloud;search,<query>"""
    if not params:
        return {
            "status": "error",
            "reason": "Usage: bd-cloud;search,<query>"
        }

    query = params[0]
    blocked = _check_quota("bd-cloud-search")
    if blocked:
        return blocked

    try:
        bearer = _get_qianfan_bearer()
        url = "https://qianfan.baidubce.com/v2/ai_search/web_search"
        payload = {
            "messages": [{"role": "user", "content": query}],
            "edition": "standard",
            "search_source": "baidu_search_v2",
            "search_recency_filter": "week",
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {bearer}",
        }
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        data = resp.json()

        references = data.get("references", [])
        sources = []
        for i, ref in enumerate(references):
            content = ref.get("content", "")
            snippet = content[:300] if len(content) > 300 else content
            sources.append({
                "title": ref.get("title", ""),
                "url": ref.get("url", ""),
                "snippet": snippet,
                "relevance": f"{max(100 - i * 15, 30)}%",
            })
        return {
            "status": "ok",
            "answer": "",
            "sources": sources,
            "count": len(sources),
        }
    except RuntimeError as e:
        return {"status": "error", "reason": str(e)}
    except Exception as e:
        logger.exception("bd-cloud search failed")
        return {"status": "error", "reason": f"Search failed: {e}"}

VIDEO_SHORT_WAIT = 15  # slightly longer than ASR — video processing is slower

@directive("bd-cloud", "video-notes", domain_alias="百度云", action_aliases={"video-notes": "视频笔记"})
def bd_cloud_video_notes(params: list[str]) -> dict:
    """bd-cloud;video-notes,<video_url>"""
    if not params:
        return {
            "status": "error",
            "reason": "Usage: bd-cloud;video-notes,<video_url>"
        }

    video_url = params[0]
    blocked = _check_quota("bd-cloud-video-notes")
    if blocked:
        return blocked

    try:
        bearer = _get_qianfan_bearer()
        create_url = "https://qianfan.baidubce.com/v2/tools/ai_note/task_create"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {bearer}",
        }
        resp = requests.post(create_url, json={"url": video_url}, headers=headers, timeout=15)
        data = resp.json()
        task_id = data.get("data", {}).get("task_id") or data.get("data")
        if not task_id:
            return {"status": "error", "reason": f"Failed to create video notes task: {data}"}

        elapsed = 0
        while elapsed < VIDEO_SHORT_WAIT:
            time.sleep(3)
            elapsed += 3
            status_data = _query_video_task(task_id, bearer)
            if status_data.get("status") == "ok":
                return status_data
            if status_data.get("status") == "error":
                return {"status": "error", "reason": status_data.get("reason", "Video notes failed")}

        internal_id = f"bd-video-{task_id}"
        try:
            from handlers.task_manager import track_task
            track_task(internal_id, "bd-cloud", "video-notes-result", [str(task_id)])
        except ImportError:
            pass

        return {
            "status": "pending",
            "task_id": internal_id,
            "external_task_id": str(task_id),
            "hint": f"Use task;status,{internal_id} to check progress",
        }

    except RuntimeError as e:
        return {"status": "error", "reason": str(e)}
    except Exception as e:
        logger.exception("bd-cloud video-notes failed")
        return {"status": "error", "reason": f"Video notes failed: {e}"}

def _query_video_task(external_task_id, bearer: str) -> dict:
    """Query video notes task status."""
    url = f"https://qianfan.baidubce.com/v2/tools/ai_note/query?task_id={external_task_id}"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {bearer}"}
    resp = requests.get(url, headers=headers, timeout=15)
    data = resp.json()

    if "data" in data and isinstance(data["data"], dict):
        status = data["data"].get("status", "")
        if status == "success" or status == "completed":
            return {"status": "ok", "result": data["data"]}
        elif status == "failed" or status == "error":
            return {"status": "error", "reason": data["data"].get("error_msg", "Video notes failed")}
    elif "show_msg" in data:
        return {"status": "error", "reason": data["show_msg"]}

    return {"status": "pending"}

@directive("bd-cloud", "video-notes-result", domain_alias="百度云", action_aliases={"video-notes-result": "视频笔记结果"})
def bd_cloud_video_notes_result(params: list[str]) -> dict:
    """bd-cloud;video-notes-result,<task_id> — called by task-manager."""
    if not params:
        return {
            "status": "error",
            "reason": "Usage: bd-cloud;video-notes-result,<task_id>"
        }

    try:
        bearer = _get_qianfan_bearer()
        result = _query_video_task(params[0], bearer)
        return result
    except RuntimeError as e:
        return {"status": "error", "reason": str(e)}
    except Exception as e:
        logger.exception("bd-cloud video-notes-result failed")
        return {"status": "error", "reason": f"Query failed: {e}"}

def init_bd_cloud_handler(db_path: str = None):
    """Initialise with SQLite DB path for key retrieval."""
    global DB_PATH
    if db_path:
        DB_PATH = {'config': db_path}
    else:
        import os
        sqlite_file = os.environ.get("SQLITE_DB_PATH", "/root/text-cli/service/text_cli_modules/sqlite/service.db")
        DB_PATH = {'config': sqlite_file}
