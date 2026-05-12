"""
AI 推理模块 — 模型回退链 + 时段感知路由

设计:
  - 零外部依赖（urllib stdlib）
  - api_keys 参数注入，不持有状态
  - 时段智能选模型 + 回退链（先便宜后贵）
  - 所有 API 走 OpenAI-compatible chat/completions 格式

模式:
  auto   — 时段感知自动选（0-6 付费模型 / 6-24 免费模型）
  fast   — 强制免费模型链
  quality— 强制付费模型链
  <name> — 直接指定模型名

依赖: text_cli_modules.key.key_registry (获取 API key)
"""

import json
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta


# ═══════════════════════════════════════════════════════════
# 模型注册表
# ═══════════════════════════════════════════════════════════

MODEL_REGISTRY = {
    'zhipu': {
        'url': 'https://open.bigmodel.cn/api/paas/v4/chat/completions',
        'key_service': 'zhipu',
        'auth_prefix': 'Bearer ',
        'models': ['glm-4-flash', 'glm-4-flash-250414'],
        'vl_models': ['GLM-4.1V-Thinking-Flash', 'glm-4v-flash'],
    },
    'xunfei': {
        'url': 'https://spark-api-open.xf-yun.com/v1/chat/completions',
        'key_service': 'xunfei',
        'auth_prefix': 'Bearer ',
        'models': ['lite'],
        'vl_models': [],
    },
    'modelscope': {
        'url': 'https://api-inference.modelscope.cn/v1',
        'key_service': 'modelscope',
        'auth_prefix': 'Bearer ',
        'models': [
            'ZhipuAI/GLM-5',
            'moonshotai/Kimi-K2.5',
            'MiniMax/MiniMax-M2.5',
            'Qwen/Qwen3-Coder-480B-A35B-Instruct',
        ],
        'vl_models': ['Qwen/Qwen3-VL-8B-Instruct'],
    },
}

# 回退链：按顺序试，先成先用
FALLBACK_FAST = ['zhipu', 'xunfei']       # 免费/便宜
FALLBACK_QUALITY = ['modelscope']          # 付费（夜间额度充裕）



# ── 允许外部配置注入（从 model_aliases.json）──
def set_model_registry(providers: dict, fallback_fast: list, fallback_quality: list):
    """从外部配置注入模型注册表，替代硬编码值"""
    global MODEL_REGISTRY, FALLBACK_FAST, FALLBACK_QUALITY
    MODEL_REGISTRY = providers
    FALLBACK_FAST = fallback_fast
    FALLBACK_QUALITY = fallback_quality


# ═══════════════════════════════════════════════════════════
# 时段检测
# ═══════════════════════════════════════════════════════════

def get_period(tz_offset: int = 8) -> int:
    """
    返回当前时段:
      1 — 0:00-6:00 (夜间，付费模型额度充裕)
      2 — 6:00-18:00 (白天)
      3 — 18:00-24:00 (晚间)
    """
    now = datetime.now(timezone(timedelta(hours=tz_offset)))
    h = now.hour
    if h < 6:
        return 1
    elif h < 18:
        return 2
    return 3


# ═══════════════════════════════════════════════════════════
# HTTP 调用
# ═══════════════════════════════════════════════════════════

def _chat_completion(messages: list[dict], model: str, url: str,
                     api_key: str, auth_prefix: str = 'Bearer ',
                     timeout: int = 60) -> dict:
    """
    调用 OpenAI-compatible chat/completions。
    返回: {'ok': True, 'content': str} | {'ok': False, 'error': str}
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
            return {'ok': False, 'error': f'{model}: 无返回内容'}
        return {'ok': True, 'content': choices[0]['message']['content']}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()[:300]
        return {'ok': False, 'error': f'{model}: HTTP {e.code} — {err_body}'}
    except Exception as e:
        return {'ok': False, 'error': f'{model}: {e}'}


# ═══════════════════════════════════════════════════════════
# 回退链推理
# ═══════════════════════════════════════════════════════════

def _try_chain(messages: list[dict], providers: list[str],
               api_keys: dict[str, str], vl: bool = False,
               target_model: str = None) -> dict:
    """
    按 providers 列表顺序尝试每个模型的每个模型。
    返回第一个成功的结果，或 {'ok': False, 'errors': [...]}
    """
    errors = []

    for provider_name in providers:
        provider = MODEL_REGISTRY.get(provider_name)
        if not provider:
            errors.append(f'{provider_name}: 未知提供者')
            continue

        api_key = api_keys.get(provider['key_service'], '')
        if not api_key:
            errors.append(f'{provider_name}: 缺少 API key ({provider["key_service"]})')
            continue

        # 确定要试的模型列表
        if target_model:
            candidates = [target_model]
        elif vl:
            candidates = provider.get('vl_models', [])
        else:
            candidates = provider['models']

        if not candidates:
            errors.append(f'{provider_name}: 无可用模型{" (VL)" if vl else ""}')
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
# 对外 API
# ═══════════════════════════════════════════════════════════

def text_inference(prompt: str, api_keys: dict[str, str],
                   mode: str = 'auto') -> dict:
    """
    纯文本推理。

    参数:
      prompt   — 推理提示词
      api_keys — {'zhipu': '...', 'xunfei': '...', 'modelscope': '...'}
      mode     — auto / fast / quality / <model_name>

    返回:
      {'ok': True, 'content': str, 'model_used': str, 'provider': str}
      | {'ok': False, 'error': str}
    """
    messages = [{'role': 'user', 'content': prompt}]

    # 解算模式 → 提供者链 + 可选指定模型
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
        # 直接指定模型名 → 在所有提供者里找
        target_model = mode
        # 找出哪个提供者有这个模型
        all_providers = list(MODEL_REGISTRY.keys())
        providers = all_providers

    result = _try_chain(messages, providers, api_keys,
                        vl=False, target_model=target_model)
    if not result['ok']:
        return {'ok': False, 'error': '; '.join(result.get('errors', ['未知错误']))}
    return result


def vision_inference(prompt: str, image_url: str,
                     api_keys: dict[str, str],
                     mode: str = 'auto') -> dict:
    """
    视觉推理（文本 + 图片）。

    参数:
      prompt    — 推理提示词
      image_url — 图片 URL (http/https) 或 base64 data URI
      api_keys  — {'zhipu': '...', 'modelscope': '...'}
      mode      — auto / fast / quality / <model_name>

    返回:
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
        return {'ok': False, 'error': '; '.join(result.get('errors', ['未知错误']))}
    return result
