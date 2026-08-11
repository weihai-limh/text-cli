"""
AI inference handler — text-cli instruction package.

Text reasoning and vision-language analysis via configurable AI provider.
Provider names and models are defined in configuration, never in code.
Supports multi-mode model selection and in-memory cache substitution.

Directives:
    ai;infer,<prompt>[,<mode>]       → text inference
    ai;vision,<prompt>,<image>[,<mode>]  → vision-language inference

Modes:
    auto (default)   → time-aware smart model chain
    fast             → free model chain
    quality          → paid model chain
    <model_name>     → direct model selection

API key read from SQLite key_registry as ai_api_key.
Register: AI:key;register,ai_api_key,<key>,api_key

Author: Tide 🌊
"""

import json
import logging
import os
import re
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    from text_cli_modules.ai import text_inference, vision_inference, get_period
    from text_cli_modules.key.key_registry import get as key_get
    AI_ENABLED = True
except ImportError as e:
    AI_ENABLED = False
    logger.info("AI module not installed: %s", e)

from core.registry import directive


_MODEL_CFG: dict | None = None
_KEY_SERVICES: list[str] = []


def _load_model_config() -> dict:
    global _MODEL_CFG, _KEY_SERVICES
    if _MODEL_CFG:
        return _MODEL_CFG
    cfg_path = Path(__file__).resolve().parent.parent.parent / "config" / "model_aliases.json"
    try:
        with open(cfg_path) as f:
            _MODEL_CFG = json.load(f)
        _KEY_SERVICES = [p["name"] for p in _MODEL_CFG.get("providers", {}).values() if p.get("name")]
        logger.info("Model config loaded: %s", _KEY_SERVICES)
    except Exception as e:
        logger.warning("Failed to load model config: %s", e)
        _MODEL_CFG = {}
    return _MODEL_CFG


DB_PATH: dict = {}
_COPILOT_KEY_PATH: str | None = None


def init_ai_handler(db_path: str):
    """Initialise AI handler with SQLite DB path and model registry."""
    global DB_PATH
    DB_PATH = {"config": db_path}
    global _COPILOT_KEY_PATH
    candidate = str(Path(__file__).resolve().parent.parent.parent / "copilot" / "data" / "key_registry.json")
    if os.path.exists(candidate):
        _COPILOT_KEY_PATH = candidate

    cfg = _load_model_config()
    if cfg:
        from text_cli_modules.ai.inference import set_model_registry
        prov = cfg.get("providers", {})
        registry = {}
        for alias_id, info in prov.items():
            name = info.get("name", "")
            if name:
                registry[name] = {
                    "url": info["url"],
                    "key_service": name,
                    "auth_prefix": info.get("auth_prefix", "Bearer "),
                    "models": info.get("models", []),
                    "vl_models": info.get("vl_models", []),
                }
        fb = cfg.get("fallback", {})
        ff_names = [prov.get(a, {}).get("name", a) for a in fb.get("fast", [])]
        fq_names = [prov.get(a, {}).get("name", a) for a in fb.get("quality", [])]
        set_model_registry(registry, ff_names, fq_names)
        logger.info("Model registry injected: %s", list(registry.keys()))


def _get_api_keys() -> dict[str, str]:
    """Read all AI-related keys with three-tier fallback:
    1. SQLite key_registry (A6 — quota tracking enabled)
    2. copilot JSON (legacy encrypted storage)
    3. Environment variables (A3 — bare-metal fallback)
    """
    keys = {}

    if DB_PATH:
        try:
            for svc in _KEY_SERVICES:
                val = key_get(DB_PATH, svc)
                if val and isinstance(val, str):
                    keys[svc] = val
        except Exception:
            pass

    if _COPILOT_KEY_PATH:
        try:
            reg = json.loads(Path(_COPILOT_KEY_PATH).read_text())
            secret = os.environ.get("KEY_REGISTRY_SECRET", "")
            for svc in _KEY_SERVICES:
                if svc in keys:
                    continue
                entry = reg.get(svc)
                if entry and "encrypted_value" in entry:
                    encrypted = entry["encrypted_value"]
                    if secret:
                        key_bytes = secret.encode("utf-8")
                        cipher = bytes.fromhex(encrypted)
                        val = "".join(
                            chr(c ^ key_bytes[i % len(key_bytes)])
                            for i, c in enumerate(cipher)
                        )
                        if val:
                            keys[svc] = val
        except Exception:
            pass

    for svc in _KEY_SERVICES:
        if svc not in keys:
            env_var = svc.upper().replace("-", "_") + "_API_KEY"
            env_val = os.environ.get(env_var, "")
            if not env_val:
                env_val = os.environ.get(svc.upper().replace("-", "_"), "")
            if env_val:
                keys[svc] = env_val

    return keys


def _mode_help() -> str:
    return (
        "Modes: auto (time-aware) / fast (free chain) / quality (paid chain)"
        " / <model_name> (direct)\n"
        "Time: 0-6h paid models / 6-24h free models"
    )


def _image_cache_get(key: str) -> str | None:
    """Guard: lazily import handlers.image.cache_get, degrade on absence."""
    try:
        from handlers.image import cache_get
        return cache_get(key)
    except (ImportError, AttributeError):
        return None


def _image_cache_put(content: str) -> str | None:
    """Guard: lazily import handlers.image._cache_put, degrade on absence."""
    try:
        from handlers.image import _cache_put
        return _cache_put(content)
    except (ImportError, AttributeError):
        return None


def _resolve_cache_refs(text: str) -> str:
    """Replace cache:<key> references with cached content."""
    def _sub(m):
        val = _image_cache_get(m.group(1))
        return val if val is not None else f"[cache expired:{m.group(1)}]"
    return re.sub(r"cache:([a-f0-9]{12,16})", _sub, text)


@directive("ai", "infer", domain_alias="AI辅助", action_aliases={"infer": "推理"})
def ai_text_reasoning(params: list[str]) -> dict:
    """Text inference with optional model selection and output caching."""
    if not AI_ENABLED:
        return {"status": "error", "reason": "AI module not installed"}

    if not params:
        return {"status": "error", "reason": f"Usage: ai;infer,<prompt>[,<mode>]\n{_mode_help()}"}

    prompt = params[0]
    mode = params[1] if len(params) > 1 else "auto"

    want_cache = False
    if "," in mode:
        parts = mode.split(",")
        mode = parts[0]
        want_cache = "cache" in parts[1:]
    if not want_cache:
        for p in params[1:]:
            if p.strip() == "cache":
                want_cache = True
                break

    resolved_prompt = _resolve_cache_refs(prompt)

    api_keys = _get_api_keys()
    if not api_keys:
        return {"status": "error", "reason": "AI keys not configured. Register: key;register,ai_api_key,<key>,api_key"}

    try:
        result = text_inference(resolved_prompt, api_keys, mode)
    except Exception as e:
        return {"status": "error", "reason": f"Inference exception: {e}"}

    if result["ok"]:
        content = result["content"]
        if want_cache:
            key = _image_cache_put(content)
            if key:
                return {"status": "ok", "result": content, "cache_key": key}
        return {"status": "ok", "result": content}
    return {"status": "error", "reason": f"Inference failed: {result['error']}"}


@directive("ai", "vision", domain_alias="AI辅助", action_aliases={"vision": "视觉"})
def ai_vision_reasoning(params: list[str]) -> dict:
    """Vision-language inference with optional output caching."""
    if not AI_ENABLED:
        return {"status": "error", "reason": "AI module not installed"}

    if len(params) < 2:
        return {
            "status": "error",
            "reason": (
                f"Usage: AI;vision,<prompt>,<image>[,<mode>]\n"
                f"Image: URL, base64 data URI, or cache:<key>\n"
                f"{_mode_help()}"
            ),
        }

    prompt = params[0]
    image_url = params[1]
    mode = params[2] if len(params) > 2 else "auto"

    want_cache = False
    if "," in mode:
        parts = mode.split(",")
        mode = parts[0]
        want_cache = "cache" in parts[1:]
    for p in params[2:]:
        if p.strip() == "cache":
            want_cache = True
            break

    resolved_prompt = _resolve_cache_refs(prompt)

    if image_url.startswith("cache:"):
        key = image_url[6:]
        data = _image_cache_get(key)
        if data is None:
            return {"status": "error", "reason": f"Cache expired or not found: {key}"}
        image_url = f"data:image/jpeg;base64,{data}"

    api_keys = _get_api_keys()
    if not api_keys:
        return {"status": "error", "reason": "AI keys not configured"}

    try:
        result = vision_inference(resolved_prompt, image_url, api_keys, mode)
    except Exception as e:
        return {"status": "error", "reason": f"Vision inference exception: {e}"}

    if result["ok"]:
        content = result["content"]
        if want_cache:
            key = _image_cache_put(content)
            if key:
                return {"status": "ok", "result": content, "cache_key": key}
        return {"status": "ok", "result": content}
    return {"status": "error", "reason": f"Vision inference failed: {result['error']}"}
