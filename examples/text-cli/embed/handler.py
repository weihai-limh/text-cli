"""
Semantic embedding handler — service edition

Directives:
  semantic;encode (alias: 语义;编码),<text>[,mode]
  semantic;similar (alias: 语义;相似),<textA>,<textB>[,mode]
  semantic;match (alias: 语义;匹配),<query>,<candidate1>,<candidate2>,...[,mode]

Mode: A=256 B=512(default) C=1024 D=2048

API key read from SQLite key_registry for bigmodel-embedding-3
"""

import logging

logger = logging.getLogger(__name__)

try:
    from text_cli_modules.embed import encode, encode_batch, similarity, match, MODE_DIMS
    from text_cli_modules.key.key_registry import get as key_get
    EMBED_ENABLED = True
except ImportError as e:
    EMBED_ENABLED = False
    logger.info("Embed module not installed: %s", e)

from core.registry import directive

DB_PATH: dict = {}
API_KEY_SERVICE = "bigmodel-embedding-3"


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
    env_val = os.environ.get(API_KEY_SERVICE.upper().replace("-", "_"), "")
    env_val = env_val or os.environ.get(API_KEY_SERVICE.upper().replace("-", "_") + "_API_KEY", "")
    return env_val


@directive("semantic", "encode", domain_alias="语义", action_aliases={"encode": "编码"})
def sem_encode(params: list[str]) -> str:
    if not EMBED_ENABLED:
        return 'Embed module not installed'

    if not params:
        return 'Insufficient params: semantic;encode (alias: 语义;编码),<text>[,mode]'

    api_key = _get_api_key()
    if not api_key:
        return f'API key not configured: {API_KEY_SERVICE}. Register via: 指令:key;register (alias: 密钥;注册),{API_KEY_SERVICE},<key>,api_key'

    text = params[0]
    mode = params[1] if len(params) > 1 else 'B'
    try:
        vec = encode(text, api_key, mode)
        dims = len(vec)
        preview = [round(v, 6) for v in vec[:8]]
        return f'Encoded ({dims} dims)\nPreview: {preview}...'
    except Exception as e:
        return f'Encode failed: {e}'


@directive("semantic", "similar", domain_alias="语义", action_aliases={"similar": "相似"})
def sem_similarity(params: list[str]) -> str:
    if not EMBED_ENABLED:
        return 'Embed module not installed'

    if len(params) < 2:
        return 'Insufficient params: semantic;similar (alias: 语义;相似),<textA>,<textB>[,mode]'

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
        return f'Similarity failed: {e}'


@directive("semantic", "match", domain_alias="语义", action_aliases={"match": "匹配"})
def sem_match(params: list[str]) -> str:
    if not EMBED_ENABLED:
        return 'Embed module not installed'

    if len(params) < 2:
        return 'Insufficient params: semantic;match (alias: 语义;匹配),<query>,<candidate1>,<candidate2>,...[,mode]'

    api_key = _get_api_key()
    if not api_key:
        return f'API key not configured: {API_KEY_SERVICE}'

    query = params[0]
    # Remove last if it's a mode param
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
        return f'Match failed: {e}'
