"""
AI 推理 handler — service 版

指令:
  AI辅助;推理,<prompt>[,模式]
  AI辅助;视觉,<prompt>,<图片>[,模式]

模式:
  auto(默认) — 时段智能选模型链
  fast       — 免费模型链
  quality    — 付费模型链
  <模型名>   — 直接指定

模型配置从 config/model_aliases.json 读取，不进代码。
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
    logger.info("AI 模块未安装: %s", e)

from core.registry import directive

# ── 模型配置 ──
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

    # 加载模型配置并注入推理引擎
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
    """从 SQLite + copilot JSON 读取所有 AI 相关密钥"""
    keys = {}

    # 1. 从 SQLite 读取
    if DB_PATH:
        for svc in _KEY_SERVICES:
            val = key_get(DB_PATH, svc)
            if val:
                keys[svc] = val

    # 2. 从 copilot JSON 回退读取
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
                        # XOR 解密（内联，避免 cross-module import）
                        key_bytes = secret.encode('utf-8')
                        cipher = bytes.fromhex(encrypted)
                        val = ''.join(chr(c ^ key_bytes[i % len(key_bytes)]) for i, c in enumerate(cipher))
                        if val:
                            keys[svc] = val
        except Exception:
            pass

    return keys


def _mode_help() -> str:
    return (
        '模式: auto(时段智能) / fast(免费链) / quality(付费链)'
        ' / 模型名(指定)\n'
        '时段: 0-6时付费模型 / 6-24时免费模型'
    )


@directive("AI辅助", "推理")
def ai_text_reasoning(params: list[str]) -> str:
    """
    AI辅助;推理,<prompt>[,模式]
    prompt 支持 cache:<key> → 自动 fetch 文本替入
    模式: auto/fast/quality/模型名[,cache] — ,cache 缓存输出
    """
    if not AI_ENABLED:
        return 'AI 模块未安装'

    if not params:
        return f'参数不足: AI辅助;推理,<prompt>[,模式]\n{_mode_help()}'

    prompt = params[0]
    mode = params[1] if len(params) > 1 else 'auto'

    # 解析模式：纯模式名 vs 逗号分隔；也检查尾部参数
    want_cache = False
    # 如果在 mode 内用逗号分隔: auto,cache
    if ',' in mode:
        parts = mode.split(',')
        mode = parts[0]
        want_cache = 'cache' in parts[1:]
    # 如果 cache 是独立参数（被逗号分隔出来）
    if not want_cache:
        for p in params[1:]:
            if p.strip() == 'cache':
                want_cache = True
                break

    # cache:<key> 在 prompt 中 → 替换为缓存文本
    resolved_prompt = prompt
    if 'cache:' in prompt:
        from handlers.image import cache_get
        def _replace_tcache(m):
            key = m.group(1)
            data = cache_get(key)
            return data if data else f'[缓存过期:{key}]'
        resolved_prompt = re.sub(r'cache:([a-f0-9]{12,16})', _replace_tcache, prompt)

    api_keys = _get_api_keys()
    if not api_keys:
        return '未配置 AI 密钥。请先注册: 密钥;注册,zhipu,<key>,api_key 等'

    try:
        result = text_inference(resolved_prompt, api_keys, mode)
    except Exception as e:
        return f'推理异常: {e}'

    if result['ok']:
        content = result['content']
        if want_cache:
            from handlers.image import _cache_put
            key = _cache_put(content)
            return f'cache:{key}\n{content}'
        return content
    else:
        return f'推理失败: {result["error"]}'


@directive("AI辅助", "视觉")
def ai_vision_reasoning(params: list[str]) -> str:
    """
    AI辅助;视觉,<prompt>,<图片>[,模式]
    prompt/图片 支持 cache:<key> → 自动 fetch 替入
    模式: auto/fast/quality/模型名[,cache] — ,cache 缓存输出
    """
    if not AI_ENABLED:
        return 'AI 模块未安装'

    if len(params) < 2:
        return (
            f'参数不足: AI辅助;视觉,<prompt>,<图片>[,模式]\n'
            f'图片支持: http/https URL, base64 data URI, 或 cache:<key>\n'
            f'{_mode_help()}'
        )

    prompt = params[0]
    image_url = params[1]
    mode = params[2] if len(params) > 2 else 'auto'

    # 解析模式
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

    # cache:<key> 在 prompt 中 → 替换为缓存文本
    resolved_prompt = prompt
    if 'cache:' in prompt:
        from handlers.image import cache_get
        def _replace_vcache(m):
            key = m.group(1)
            data = cache_get(key)
            return data if data else f'[缓存过期:{key}]'
        resolved_prompt = re.sub(r'cache:([a-f0-9]{12,16})', _replace_vcache, prompt)

    # cache:<key> 作为图片 → 从本地缓存读取 base64
    if image_url.startswith('cache:'):
        from handlers.image import cache_get
        key = image_url[6:]
        data = cache_get(key)
        if data is None:
            return f'缓存已过期或不存在: {key}'
        image_url = f'data:image/jpeg;base64,{data}'

    api_keys = _get_api_keys()
    if not api_keys:
        return '未配置 AI 密钥'

    try:
        result = vision_inference(resolved_prompt, image_url, api_keys, mode)
    except Exception as e:
        return f'视觉推理异常: {e}'

    if result['ok']:
        content = result['content']
        if want_cache:
            from handlers.image import _cache_put
            key = _cache_put(content)
            return f'cache:{key}\n{content}'
        return content
    else:
        return f'视觉推理失败: {result["error"]}'
