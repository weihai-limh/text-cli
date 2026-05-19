"""
AI generation handler — text-cli instruction package.

Image and video generation via configurable AI provider.
Provider names and models are defined in configuration, never in code.
Video generation is async with polling.

Directives:
    image-gen;generate,<prompt>[,<size>]          → image URL
    video;generate,<prompt>[,<size>[,<quality>]]  → task ID (async)
    video;status,<task_id>                        → poll result

Config loaded from config/model_aliases.json.
API key shared with ai_inference handler (requires ai_inference installed).
"""

import hashlib
import json
import time
import urllib.error
import urllib.request

from pathlib import Path as _Path

from core.registry import directive

# ── Config ───────────────────────────────────────

_GEN_CFG: dict = {}


def _load_gen_config():
    global _GEN_CFG
    if _GEN_CFG:
        return _GEN_CFG
    cfg_path = _Path(__file__).resolve().parent.parent / "config" / "model_aliases.json"
    try:
        with open(cfg_path) as f:
            cfg = json.load(f)
        gen = cfg.get("generation", {})
        _GEN_CFG = {
            "image_model": gen.get("image", {}).get("model", "default-image-model"),
            "image_api": gen.get("image", {}).get("api_url", ""),
            "video_model": gen.get("video", {}).get("model", "default-video-model"),
            "video_api": gen.get("video", {}).get("api_url", ""),
            "video_status_api": gen.get("video", {}).get("status_url", ""),
        }
        return _GEN_CFG
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Failed to load gen config: %s", e)
        return {}


_load_gen_config()


# ── Key resolution ───────────────────────────────

def _get_api_key() -> str | None:
    """Obtain API key via ai_inference handler or environment variable."""
    try:
        from handlers.ai_inference import _get_api_keys
        keys = _get_api_keys()
        if keys.get("ai_api_key"):
            return keys["ai_api_key"]
    except Exception:
        pass

    # Fallback to environment (A3)
    return os.environ.get("AI_API_KEY") or os.environ.get("AI_PROVIDER_KEY", "") or None


def _http_post(url: str, body: dict, timeout: int = 120) -> dict:
    api_key = _get_api_key()
    if not api_key:
        return {"error": "AI provider API key not configured"}

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


# ── Directives ───────────────────────────────────

@directive("image-gen", "generate", domain_alias="图像", action_aliases={"generate": "生成"})
def image_generate(params: list[str]) -> str:
    """Generate an image via configurable model."""
    if not params:
        return "Usage: image-gen;generate,<prompt>[,<size>]"

    prompt = params[0]
    size = "1280x1280"
    if len(params) > 1 and params[1]:
        size = params[1]

    result = _http_post(_GEN_CFG.get("image_api", ""), {
        "model": _GEN_CFG.get("image_model", "default-image-model"),
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
    """Submit an async video generation task via configurable model."""
    if not params:
        return "Usage: video;generate,<prompt>[,<size>[,<quality>]]"

    prompt = params[0]
    size = "1920x1080"
    quality = "quality"
    if len(params) > 1 and params[1]:
        size = params[1]
    if len(params) > 2 and params[2]:
        quality = params[2]

    result = _http_post(_GEN_CFG.get("video_api", ""), {
        "model": _GEN_CFG.get("video_model", "default-video-model"),
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
    """Poll the status of an async video generation task."""
    if not params:
        return "Usage: video;status,<task_id>"

    task_id = params[0]
    url = _GEN_CFG.get("video_status_api", "").format(task_id=task_id)
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
