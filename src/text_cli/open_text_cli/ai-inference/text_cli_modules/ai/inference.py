"""
AI inference module — model fallback chain + time-aware routing.

Design:
  - Zero external dependencies (urllib stdlib only)
  - API keys are injected via the api_keys parameter; this module holds no state
  - Time-aware model selection + fallback chain (cheap first, then premium)
  - All provider calls use the OpenAI-compatible chat/completions format

Modes:
  auto   — time-aware auto-select (paid models 0-6h / free models 6-24h)
  fast   — force the free-model chain
  quality— force the paid-model chain
  <name> — specify a model name directly

Dependency: text_cli_modules.key.key_registry (API key retrieval)

DISTRIBUTION NOTE:
  This package ships NO concrete providers. The default MODEL_REGISTRY is
  empty. Providers and models are injected at runtime via set_model_registry()
  (typically from config/model_aliases.json by handler.init_ai_handler()).
  Populate that config with YOUR OWN endpoints and models before use.
"""

import json
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta


# Distributed package ships NO concrete providers.
# MODEL_REGISTRY is injected at runtime via set_model_registry().
MODEL_REGISTRY: dict = {}

# Fallback chains are also injected at runtime; empty by default.
FALLBACK_FAST: list = []
FALLBACK_QUALITY: list = []


def set_model_registry(providers: dict, fallback_fast: list, fallback_quality: list):
    """Inject the provider registry and fallback chains at runtime."""
    global MODEL_REGISTRY, FALLBACK_FAST, FALLBACK_QUALITY
    MODEL_REGISTRY = providers
    FALLBACK_FAST = fallback_fast
    FALLBACK_QUALITY = fallback_quality


def get_period(tz_offset: int = 8) -> int:
    """Return the current time period (1=late night, 2=day, 3=evening)."""
    now = datetime.now(timezone(timedelta(hours=tz_offset)))
    h = now.hour
    if h < 6:
        return 1
    elif h < 18:
        return 2
    return 3


def _chat_completion(messages: list[dict], model: str, url: str,
                     api_key: str, auth_prefix: str = 'Bearer ',
                     timeout: int = 60) -> dict:
    """Call an OpenAI-compatible chat/completions endpoint."""
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
            return {'ok': False, 'error': f'{model}: no content returned'}
        return {'ok': True, 'content': choices[0]['message']['content']}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()[:300]
        return {'ok': False, 'error': f'{model}: HTTP {e.code} — {err_body}'}
    except Exception as e:
        return {'ok': False, 'error': f'{model}: {e}'}


def _try_chain(messages: list[dict], providers: list[str],
               api_keys: dict[str, str], vl: bool = False,
               target_model: str = None) -> dict:
    """Walk the provider chain, trying each candidate model until one succeeds."""
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
            errors.append(f'{provider_name}: no available model{" (VL)" if vl else ""}')
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


def text_inference(prompt: str, api_keys: dict[str, str],
                   mode: str = 'auto') -> dict:
    """Run text inference with multi-mode model selection and fallback."""
    if not MODEL_REGISTRY:
        return {'ok': False, 'error': 'No AI providers configured. Populate '
                'config/model_aliases.json and call init_ai_handler() / '
                'set_model_registry().'}

    messages = [{'role': 'user', 'content': prompt}]

    target_model = None
    if mode in ('auto',):
        period = get_period()
        if period == 1:
            providers = FALLBACK_QUALITY
        else:
            providers = FALLBACK_FAST
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
    """Run vision-language inference (text + image) with fallback."""
    if not MODEL_REGISTRY:
        return {'ok': False, 'error': 'No AI providers configured. Populate '
                'config/model_aliases.json and call init_ai_handler() / '
                'set_model_registry().'}

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
        if period == 1:
            providers = FALLBACK_QUALITY
        else:
            providers = FALLBACK_FAST
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
