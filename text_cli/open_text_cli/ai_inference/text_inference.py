"""
AI inference module — model fallback chain with configurable providers.

Design:
  - Zero external dependencies (stdlib urllib)
  - API keys injected via params, no state held
  - Configurable fallback chain (try cheap first, then quality)
  - All APIs use OpenAI-compatible chat/completions format

Modes:
  auto    — default fallback chain
  fast    — fast/cheap provider chain
  quality — high-quality provider chain
  <name>  — directly specify model name

Dependency: text_cli_modules.key.key_registry (API key retrieval)
"""

import json
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta


# ═══════════════════════════════════════════════════════════
# Model Registry (template — override via model_aliases.json)
# ═══════════════════════════════════════════════════════════

MODEL_REGISTRY: dict = {}
FALLBACK_FAST: list[str] = []
FALLBACK_QUALITY: list[str] = []


def set_model_registry(providers: dict, fallback_fast: list, fallback_quality: list):
    """Inject model registry from external config, replacing defaults."""
    global MODEL_REGISTRY, FALLBACK_FAST, FALLBACK_QUALITY
    MODEL_REGISTRY = providers
    FALLBACK_FAST = fallback_fast
    FALLBACK_QUALITY = fallback_quality


# ═══════════════════════════════════════════════════════════
# Time-period detection
# ═══════════════════════════════════════════════════════════

def get_period(tz_offset: int = 8) -> int:
    """Return current time period.

    1 — night (0:00-6:00, quality quota充裕)
    2 — day (6:00-18:00)
    3 — evening (18:00-24:00)
    """
    now = datetime.now(timezone(timedelta(hours=tz_offset)))
    h = now.hour
    if h < 6:
        return 1
    elif h < 18:
        return 2
    return 3


# ═══════════════════════════════════════════════════════════
# HTTP call
# ═══════════════════════════════════════════════════════════

def _chat_completion(messages: list[dict], model: str, url: str,
                     api_key: str, auth_prefix: str = 'Bearer ',
                     timeout: int = 60) -> dict:
    """Call OpenAI-compatible chat/completions endpoint.

    Returns: {'ok': True, 'content': str} | {'ok': False, 'error': str}
    """
    body = json.dumps({
        'model': model,
        'messages': messages,
        'stream': False,
    }).encode('utf-8')

    req = urllib.request.Request(url, data=body, headers={
        'Content-Type': 'application/json',
        'Authorization': f'{auth_prefix}{api_key}',
    })

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
        choices = data.get('choices', [])
        if not choices:
            return {'ok': False, 'error': f'{model}: empty response'}
        return {'ok': True, 'content': choices[0]['message']['content']}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()[:300]
        return {'ok': False, 'error': f'{model}: HTTP {e.code} — {err_body}'}
    except Exception as e:
        return {'ok': False, 'error': f'{model}: {e}'}


# ═══════════════════════════════════════════════════════════
# Fallback-chain inference
# ═══════════════════════════════════════════════════════════

def _try_chain(messages: list[dict], providers: list[str],
               api_keys: dict[str, str], vl: bool = False,
               target_model: str = None) -> dict:
    """Try each provider's models in order. Return first success."""
    errors = []

    for provider_name in providers:
        provider = MODEL_REGISTRY.get(provider_name)
        if not provider:
            errors.append(f'{provider_name}: unknown provider')
            continue

        api_key = api_keys.get(provider['key_service'], '')
        if not api_key:
            errors.append(f'{provider_name}: missing API key ({provider["key_service"]})')
            continue

        if target_model:
            candidates = [target_model]
        elif vl:
            candidates = provider.get('vl_models', [])
        else:
            candidates = provider['models']

        if not candidates:
            errors.append(f'{provider_name}: no models available{" (VL)" if vl else ""}')
            continue

        for model in candidates:
            result = _chat_completion(
                messages, model, provider['url'], api_key,
                provider.get('auth_prefix', 'Bearer '),
            )
            if result['ok']:
                result['model_used'] = model
                result['provider'] = provider_name
                return result
            errors.append(result['error'])

    return {'ok': False, 'errors': errors}


# ═══════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════

def text_inference(prompt: str, api_keys: dict[str, str],
                   mode: str = 'auto') -> dict:
    """Plain text inference.

    Args:
        prompt   — inference prompt
        api_keys — provider API keys dict
        mode     — auto / fast / quality / <model_name>

    Returns:
        {'ok': True, 'content': str, 'model_used': str, 'provider': str}
        | {'ok': False, 'error': str}
    """
    messages = [{'role': 'user', 'content': prompt}]

    target_model = None
    if mode in ('auto',):
        period = get_period()
        providers = FALLBACK_QUALITY if period == 1 else FALLBACK_FAST
    elif mode == 'fast':
        providers = FALLBACK_FAST
    elif mode == 'quality':
        providers = FALLBACK_QUALITY
    else:
        target_model = mode
        providers = list(MODEL_REGISTRY.keys())

    result = _try_chain(messages, providers, api_keys,
                        vl=False, target_model=target_model)
    if not result['ok']:
        return {'ok': False, 'error': '; '.join(result.get('errors', ['unknown error']))}
    return result


def vision_inference(prompt: str, image_url: str,
                     api_keys: dict[str, str],
                     mode: str = 'auto') -> dict:
    """Vision-language inference (text + image).

    Args:
        prompt    — inference prompt
        image_url — image URL (http/https) or base64 data URI
        api_keys  — provider API keys dict
        mode      — auto / fast / quality / <model_name>

    Returns:
        {'ok': True, 'content': str, 'model_used': str, 'provider': str}
        | {'ok': False, 'error': str}
    """
    messages = [{
        'role': 'user',
        'content': [
            {'type': 'text', 'text': prompt},
            {'type': 'image_url', 'image_url': {'url': image_url}},
        ],
    }]

    target_model = None
    if mode == 'auto':
        period = get_period()
        providers = FALLBACK_QUALITY if period == 1 else FALLBACK_FAST
    elif mode == 'fast':
        providers = FALLBACK_FAST
    elif mode == 'quality':
        providers = FALLBACK_QUALITY
    else:
        target_model = mode
        providers = list(MODEL_REGISTRY.keys())

    result = _try_chain(messages, providers, api_keys,
                        vl=True, target_model=target_model)
    if not result['ok']:
        return {'ok': False, 'error': '; '.join(result.get('errors', ['unknown error']))}
    return result
