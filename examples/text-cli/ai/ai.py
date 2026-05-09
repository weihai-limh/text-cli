"""
AI辅助 — 多模型回退链推理

模式:
  auto   — 时段感知自动选（0-6时付费模型 / 6-24时免费模型）
  fast   — 强制免费模型链
  quality— 强制付费模型链
  <name> — 直接指定模型名

提供者: zhipu (GLM-4) / xunfei (Spark Lite) / modelscope (多模型)

依赖: urllib (stdlib only)
弹性: api_keys 参数注入，零状态，纯函数
"""

import json
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

MODEL_REGISTRY = {
    'zhipu': {
        'url': 'https://open.bigmodel.cn/api/paas/v4/chat/completions',
        'key_service': 'zhipu',
        'models': ['glm-4-flash', 'glm-4-flash-250414'],
        'vl_models': ['glm-4v-flash', 'glm-4.6v-flash'],
    },
    'xunfei': {
        'url': 'https://spark-api-open.xf-yun.com/v1/chat/completions',
        'key_service': 'xunfei',
        'models': ['lite'],
        'vl_models': [],
    }
}

FALLBACK_FAST = ['zhipu', 'xunfei']
FALLBACK_QUALITY = ['']


def get_period(tz_offset: int = 8) -> int:
    """1=夜间(0-6) 2=白天(6-18) 3=晚间(18-24)"""
    h = datetime.now(timezone(timedelta(hours=tz_offset))).hour
    if h < 6: return 1
    if h < 18: return 2
    return 3


def _chat_completion(messages, model, url, api_key, auth_prefix='Bearer ', timeout=60):
    body = json.dumps({'model': model, 'messages': messages, 'stream': False}).encode()
    req = urllib.request.Request(url, data=body, headers={
        'Content-Type': 'application/json',
        'Authorization': f'{auth_prefix}{api_key}',
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
        content = data['choices'][0]['message']['content']
        return {'ok': True, 'content': content, 'model_used': model}
    except Exception as e:
        return {'ok': False, 'error': f'{model}: {e}'}


def _try_chain(messages, providers, api_keys, vl=False, target_model=None):
    errors = []
    for pn in providers:
        p = MODEL_REGISTRY.get(pn)
        if not p: errors.append(f'{pn}: 未知'); continue
        ak = api_keys.get(p['key_service'], '')
        if not ak: errors.append(f'{pn}: 缺少key'); continue

        candidates = [target_model] if target_model else (p.get('vl_models', []) if vl else p['models'])
        for model in candidates:
            r = _chat_completion(messages, model, p['url'], ak)
            if r['ok']:
                r['provider'] = pn
                return r
            errors.append(r['error'])
    return {'ok': False, 'errors': errors}


def text_inference(prompt, api_keys, mode='auto'):
    messages = [{'role': 'user', 'content': prompt}]
    target = None
    if mode == 'auto':
        providers = FALLBACK_QUALITY if get_period() == 1 else FALLBACK_FAST
    elif mode == 'fast':
        providers = FALLBACK_FAST
    elif mode == 'quality':
        providers = FALLBACK_QUALITY
    else:
        target = mode; providers = list(MODEL_REGISTRY.keys())
    r = _try_chain(messages, providers, api_keys, target_model=target)
    if r['ok']: return r
    return {'ok': False, 'error': '; '.join(r.get('errors', []))}


def vision_inference(prompt, image_url, api_keys, mode='auto'):
    messages = [{'role': 'user', 'content': [
        {'type': 'text', 'text': prompt},
        {'type': 'image_url', 'image_url': {'url': image_url}},
    ]}]
    target = None
    if mode == 'auto':
        providers = FALLBACK_QUALITY if get_period() == 1 else FALLBACK_FAST
    elif mode == 'fast':
        providers = FALLBACK_FAST
    elif mode == 'quality':
        providers = FALLBACK_QUALITY
    else:
        target = mode; providers = list(MODEL_REGISTRY.keys())
    r = _try_chain(messages, providers, api_keys, vl=True, target_model=target)
    if r['ok']: return r
    return {'ok': False, 'error': '; '.join(r.get('errors', []))}
