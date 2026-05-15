"""
Image / video generation handlers.

Configuration loaded from model_aliases.json at startup.
Models and API endpoints are configurable — no hardcoded provider references.

Directives:
    image-gen;generate,<prompt>[,size] → image URL
    video;generate,<prompt>[,size,quality] → task ID (async)
    video;status,<task_id> → poll result
"""

import json
import urllib.request
import urllib.error
from pathlib import Path as _Path

from core.registry import directive

# ── Config (loaded from model_aliases.json) ──

_GEN_CFG: dict = {}


def _load_gen_config():
    """Load generation config from model_aliases.json.

    Expected format:
    {
      "generation": {
        "image": {"model": "...", "api_url": "..."},
        "video": {"model": "...", "api_url": "...", "status_url": "..."}
      }
    }
    """
    global _GEN_CFG
    if _GEN_CFG:
        return _GEN_CFG
    cfg_path = _Path(__file__).resolve().parent.parent / "config" / "model_aliases.json"
    try:
        with open(cfg_path) as f:
            cfg = json.load(f)
        gen = cfg.get("generation", {})
        _GEN_CFG = {
            "image_model": gen.get("image", {}).get("model", ""),
            "image_api": gen.get("image", {}).get("api_url", ""),
            "video_model": gen.get("video", {}).get("model", ""),
            "video_api": gen.get("video", {}).get("api_url", ""),
            "video_status_api": gen.get("video", {}).get("status_url", ""),
        }
        return _GEN_CFG
    except Exception as e:
        logger = __import__("logging").getLogger(__name__)
        logger.warning("Failed to load gen config: %s", e)
        return {}


_load_gen_config()


def _get_api_key() -> str | None:
    """Obtain API key with three-tier fallback:
    1. AI inference handler (SQLite key_registry, A6)
    2. Copilot JSON (via ai_inference)
    3. Environment variable (A3 bare-metal)
    """
    try:
        from handlers.ai_inference import _get_api_keys
        keys = _get_api_keys()
        for key in keys.values():
            if key:
                return key
    except Exception:
        pass

    # Fallback to environment
    import os
    return os.environ.get("ZHIPU_API_KEY") or os.environ.get("ZHIPU", "") or None


def _http_post(url: str, body: dict, timeout: int = 120) -> dict:
    """POST JSON to an API endpoint with Bearer auth."""
    api_key = _get_api_key()
    if not api_key:
        return {"error": "API key not configured"}

    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        return {"error": f"HTTP {e.code}: {err_body[:300]}"}
    except Exception as e:
        return {"error": str(e)}


@directive("image-gen", "generate", domain_alias="图像", action_aliases={"generate": "生成"})
def image_generate(params: list[str]) -> str:
    """Generate an image from a text prompt.

    Usage: image-gen;generate,<prompt>[,size]
    Returns: image URL
    """
    if not params:
        return "Missing params: prompt [,size]"

    prompt = params[0]
    size = params[1] if len(params) > 1 and params[1] else "1024x1024"

    model = _GEN_CFG.get("image_model", "")
    api_url = _GEN_CFG.get("image_api", "")
    if not api_url:
        return "Image generation API not configured (model_aliases.json)"

    result = _http_post(api_url, {
        "model": model,
        "prompt": prompt,
        "size": size,
    }, timeout=60)

    if "error" in result:
        return f"Image generation failed: {result['error']}"

    data_list = result.get("data", [])
    if not data_list:
        return "Image generation returned empty result"

    url = data_list[0].get("url", "")
    if not url:
        return "Image generation returned no URL"

    return f"Generation succeeded\nURL: {url}\nSize: {size}\nPrompt: {prompt}"


@directive("video", "generate", domain_alias="视频", action_aliases={"generate": "生成"})
def video_generate(params: list[str]) -> str:
    """Submit an async video generation task.

    Usage: video;generate,<prompt>[,size,quality]
    Returns: task ID for polling via video;status
    """
    if not params:
        return "Missing params: prompt [,size,quality]"

    prompt = params[0]
    size = params[1] if len(params) > 1 and params[1] else "1920x1080"
    quality = params[2] if len(params) > 2 and params[2] else "standard"

    model = _GEN_CFG.get("video_model", "")
    api_url = _GEN_CFG.get("video_api", "")
    if not api_url:
        return "Video generation API not configured (model_aliases.json)"

    result = _http_post(api_url, {
        "model": model,
        "prompt": prompt,
        "quality": quality,
        "with_audio": True,
        "size": size,
        "fps": 30,
    }, timeout=120)

    if "error" in result:
        return f"Video generation failed: {result['error']}"

    task_id = result.get("id", "")
    task_status = result.get("task_status", "UNKNOWN")

    return (
        f"Video task submitted\n"
        f"task_id: {task_id}\n"
        f"status: {task_status}\n"
        f"Prompt: {prompt}\n"
        f"Size: {size}"
    )


@directive("video", "status", domain_alias="视频", action_aliases={"status": "状态"})
def video_status(params: list[str]) -> str:
    """Poll video generation task status.

    Usage: video;status,<task_id>
    Returns: status + video URL on completion
    """
    if not params:
        return "Missing param: task_id"

    task_id = params[0]
    status_url_tpl = _GEN_CFG.get("video_status_api", "")
    if not status_url_tpl:
        return "Video status API not configured (model_aliases.json)"

    url = status_url_tpl.format(task_id=task_id)
    result = _http_post(url, {}, timeout=30)

    if "error" in result:
        return f"Query failed: {result['error']}"

    status = result.get("task_status", "UNKNOWN")
    if status == "SUCCESS":
        video_url = result.get("video_result", [{}])[0].get("url", "")
        return f"status: SUCCESS\nvideo_url: {video_url}"
    elif status == "FAIL":
        return f"status: FAIL\nReason: {result.get('error', 'unknown')}"
    else:
        return f"status: {status}\ntask_id: {task_id}"
