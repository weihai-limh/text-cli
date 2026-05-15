"""
AI inference handler — service edition

Directives:
  ai;infer (alias: AI辅助;推理),<prompt>[,mode]
  ai;vision (alias: AI辅助;视觉),<prompt>,<image>[,mode]

Modes:
  auto(default) — time-slot intelligent model chain
  fast         — free model chain
  quality      — paid model chain
  <model_name> — direct model selection

Model config loaded from config/model_aliases.json, not hardcoded.
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

# ── Model config ──
_MODEL_CFG: dict | None = None
_KEY_SERVICES: list[str] = []


def _load_model_config() -> dict:
    global _MODEL_CFG, _KEY_SERVICES
    if _MODEL_CFG:
        return _MODEL_CFG
    cfg_path = Path(__file__).resolve().parent.parent / "config" / "model_aliases.json"
    try:
        with open(cfg_path) as f:
            _MODEL_CFG = json.load(f)
        _KEY_SERVICES = [p["name"] for p in _MODEL_CFG.get("providers", {}).values() if p.get("name")]
        logger.info(f"Model config loaded: {_KEY_SERVICES}")
    except Exception as e:
        logger.warning(f"Failed to load model config: {e}")
        _MODEL_CFG = {}
    return _MODEL_CFG


DB_PATH: dict = {}
_COPILOT_KEY_PATH: str | None = None


def init_ai_handler(db_path: str):
    global DB_PATH
    DB_PATH = {'config': db_path}
    global _COPILOT_KEY_PATH
    candidate = '../text-cli-copilot/data/key_registry.json'
    if os.path.exists(candidate):
        _COPILOT_KEY_PATH = candidate

    # Load model config and inject into inference engine
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
        logger.info(f"Model registry injected: {list(registry.keys())}")


def _get_api_keys() -> dict[str, str]:
    """Read all AI-related keys from SQLite + copilot JSON"""
    keys = {}

    # 1. Read from SQLite
    if DB_PATH:
        for svc in _KEY_SERVICES:
            val = key_get(DB_PATH, svc)
            if val:
                keys[svc] = val

    # 2. Fallback to copilot JSON
    if _COPILOT_KEY_PATH:
        try:
            import json
            from pathlib import Path
            reg = json.loads(Path(_COPILOT_KEY_PATH).read_text())
            secret = os.environ.get('KEY_REGISTRY_SECRET', '')
            for svc in _KEY_SERVICES:
                if svc in keys:
                    continue
                entry = reg.get(svc)
                if entry and 'encrypted_value' in entry:
                    encrypted = entry['encrypted_value']
                    if secret:
                        # XOR decrypt (inline, avoid cross-module import)
                        key_bytes = secret.encode('utf-8')
                        cipher = bytes.fromhex(encrypted)
                        val = ''.join(chr(c ^ key_bytes[i % len(key_bytes)]) for i, c in enumerate(cipher))
                        if val:
                            keys[svc] = val
        except Exception:
            pass

    # 3. Fallback to environment variables (A3 bare-metal)
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
        'Mode: auto(time-slot) / fast(free chain) / quality(paid chain)'
        ' / model_name(direct)\n'
        'Time slot: 0-6h paid models / 6-24h free models'
    )


@directive("ai", "infer", domain_alias="AI辅助", action_aliases={"infer": "推理"})
def ai_text_reasoning(params: list[str]) -> str:
    """
    ai;infer (alias: AI辅助;推理),<prompt>[,mode]
    prompt supports cache:<key> → auto-fetch text substitution
    Mode: auto/fast/quality/model_name[,cache] — ,cache caches output
    """
    if not AI_ENABLED:
        return 'AI module not installed'

    if not params:
        return f'Insufficient params: ai;infer (alias: AI辅助;推理),<prompt>[,mode]\n{_mode_help()}'

    prompt = params[0]
    mode = params[1] if len(params) > 1 else 'auto'

    # Parse mode: plain mode name vs comma-separated; also check trailing params
    want_cache = False
    # If mode uses comma separation: auto,cache
    if ',' in mode:
        parts = mode.split(',')
        mode = parts[0]
        want_cache = 'cache' in parts[1:]
    # If cache is a separate param (split by comma)
    if not want_cache:
        for p in params[1:]:
            if p.strip() == 'cache':
                want_cache = True
                break

    # cache:<key> in prompt → substitute with cached text
    resolved_prompt = prompt
    if 'cache:' in prompt:
        from handlers.image import cache_get
        def _replace_tcache(m):
            key = m.group(1)
            data = cache_get(key)
            return data if data else f'[cache expired:{key}]'
        resolved_prompt = re.sub(r'cache:([a-f0-9]{12,16})', _replace_tcache, prompt)

    api_keys = _get_api_keys()
    if not api_keys:
        return 'AI keys not configured. Register via: key;register (alias: 密钥;注册),zhipu,<key>,api_key etc.'

    try:
        result = text_inference(resolved_prompt, api_keys, mode)
    except Exception as e:
        return f'Inference error: {e}'

    if result['ok']:
        content = result['content']
        if want_cache:
            from handlers.image import _cache_put
            key = _cache_put(content)
            return f'cache:{key}\n{content}'
        return content
    else:
        return f'Inference failed: {result["error"]}'


@directive("ai", "vision", domain_alias="AI辅助", action_aliases={"vision": "视觉"})
def ai_vision_reasoning(params: list[str]) -> str:
    """
    ai;vision (alias: AI辅助;视觉),<prompt>,<image>[,mode]
    prompt/image support cache:<key> → auto-fetch substitution
    Mode: auto/fast/quality/model_name[,cache] — ,cache caches output
    """
    if not AI_ENABLED:
        return 'AI module not installed'

    if len(params) < 2:
        return (
            f'Insufficient params: ai;vision (alias: AI辅助;视觉),<prompt>,<image>[,mode]\n'
            f'Image support: http/https URL, base64 data URI, or cache:<key>\n'
            f'{_mode_help()}'
        )

    prompt = params[0]
    image_url = params[1]
    mode = params[2] if len(params) > 2 else 'auto'

    # Parse mode
    want_cache = False
    if ',' in mode:
        parts = mode.split(',')
        mode = parts[0]
        want_cache = 'cache' in parts[1:]
    if not want_cache:
        for p in params[2:]:
            if p.strip() == 'cache':
                want_cache = True
                break

    # cache:<key> in prompt → substitute with cached text
    resolved_prompt = prompt
    if 'cache:' in prompt:
        from handlers.image import cache_get
        def _replace_vcache(m):
            key = m.group(1)
            data = cache_get(key)
            return data if data else f'[cache expired:{key}]'
        resolved_prompt = re.sub(r'cache:([a-f0-9]{12,16})', _replace_vcache, prompt)

    # cache:<key> as image → read base64 from local cache
    if image_url.startswith('cache:'):
        from handlers.image import cache_get
        key = image_url[6:]
        data = cache_get(key)
        if data is None:
            return f'Cache expired or not found: {key}'
        image_url = f'data:image/jpeg;base64,{data}'

    api_keys = _get_api_keys()
    if not api_keys:
        return 'AI keys not configured'

    try:
        result = vision_inference(resolved_prompt, image_url, api_keys, mode)
    except Exception as e:
        return f'Vision inference error: {e}'

    if result['ok']:
        content = result['content']
        if want_cache:
            from handlers.image import _cache_put
            key = _cache_put(content)
            return f'cache:{key}\n{content}'
        return content
    else:
        return f'Vision inference failed: {result["error"]}'
