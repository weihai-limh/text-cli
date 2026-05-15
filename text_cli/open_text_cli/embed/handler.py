"""
Semantic embedding handler — service edition

Directives:
  semantic;encode,<text>[,mode]
  semantic;similar,<textA>,<textB>[,mode]
  semantic;match,<query>,<candidate1>,<candidate2>,...[,mode]

Modes: A=256 B=512(default) C=1024 D=2048

API key read from SQLite key_registry
"""

import logging

logger = logging.getLogger(__name__)

try:
    from text_cli_modules.embed import encode, encode_batch, similarity, match, MODE_DIMS
    from text_cli_modules.key.key_registry import get as key_get
    EMBED_ENABLED = True
except ImportError as e:
    EMBED_ENABLED = False
    logger.info("Embedding module not installed: %s", e)

from core.registry import directive

DB_PATH: dict = {}
API_KEY_SERVICE = "your-embedding-service"


def init_embed_handler(db_path: str):
    global DB_PATH
    DB_PATH = {'config': db_path}


def _get_api_key() -> str:
    if DB_PATH:
        try:
            val = key_get(DB_PATH, API_KEY_SERVICE)
            if val and isinstance(val, str):
                return val
        except Exception:
            pass

    # Fallback to environment (A3)
    import os
    env_val = os.environ.get(API_KEY_SERVICE.upper().replace("-", "_"), "")
    env_val = env_val or os.environ.get(API_KEY_SERVICE.upper().replace("-", "_") + "_API_KEY", "")
    return env_val


@directive("semantic", "encode", domain_alias="语义", action_aliases={"encode": "编码"})
def sem_encode(params: list[str]) -> str:
    if not EMBED_ENABLED:
        return 'Embedding module not installed'

    if not params:
        return 'Missing params: semantic;encode,<text>[,mode]'

    api_key = _get_api_key()
    if not api_key:
        return f'API key not configured: {API_KEY_SERVICE}. Use directive:key;register,{API_KEY_SERVICE},<key>,api_key'

    text = params[0]
    mode = params[1] if len(params) > 1 else 'B'
    full_output = "--full" in params
    try:
        vec = encode(text, api_key, mode)
        dims = len(vec)
        preview = [round(v, 6) for v in vec[:8]]
        result = f'Encoded ({dims}d)\nPreview: {preview}...'
        if full_output:
            result += f'\nFull: {vec}'
        return result
    except Exception as e:
        return f'Encode failed: {e}'


@directive("semantic", "similar", domain_alias="语义", action_aliases={"similar": "相似"})
def sem_similarity(params: list[str]) -> str:
    if not EMBED_ENABLED:
        return 'Embedding module not installed'

    if len(params) < 2:
        return 'Missing params: semantic;similar,<textA>,<textB>[,mode]'

    api_key = _get_api_key()
    if not api_key:
        return f'API key not configured: {API_KEY_SERVICE}'

    a = params[0]
    b = params[1]
    mode = params[2] if len(params) > 2 else 'B'
    try:
        r = similarity(a, b, api_key, mode)
        return f"Similarity: {r['score']*100:.1f}%\nVerdict: {r['verdict']}"
    except Exception as e:
        return f'Semantic similarity failed: {e}'


@directive("semantic", "match", domain_alias="语义", action_aliases={"match": "匹配"})
def sem_match(params: list[str]) -> str:
    if not EMBED_ENABLED:
        return 'Embedding module not installed'

    if len(params) < 2:
        return 'Missing params: semantic;match,<query>,<candidate1>,<candidate2>,...[,mode]'

    api_key = _get_api_key()
    if not api_key:
        return f'API key not configured: {API_KEY_SERVICE}'

    query = params[0]
    # Last param is mode if it matches a known mode key
    mode = 'B'
    candidates = list(params[1:])
    if candidates and candidates[-1].upper() in MODE_DIMS:
        mode = candidates.pop().upper()

    if not candidates:
        return 'Please provide at least one candidate'

    try:
        r = match(query, candidates, api_key, mode)
        best = r['best']
        lines = [f"Best match ({best['score']*100:.1f}%): {best['text']}"]
        if len(r['ranking']) > 1:
            lines.append('')
            for i, item in enumerate(r['ranking']):
                lines.append(f"  {i+1}. [{item['score']*100:.1f}%] {item['text']}")
        return '\n'.join(lines)
    except Exception as e:
        return f'Semantic match failed: {e}'
