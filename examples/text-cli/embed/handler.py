"""
语义嵌入 handler — service 版

指令:
  语义;编码,<文本>[,模式]
  语义;相似,<文本A>,<文本B>[,模式]
  语义;匹配,<查询>,<候选1>,<候选2>,...[,模式]

模式: A=256 B=512(默认) C=1024 D=2048

密钥从 SQLite key_registry 读取 bigmodel-embedding-3
"""

import logging

logger = logging.getLogger(__name__)

try:
    from text_cli_modules.embed import encode, encode_batch, similarity, match, MODE_DIMS
    from text_cli_modules.key.key_registry import get as key_get
    EMBED_ENABLED = True
except ImportError as e:
    EMBED_ENABLED = False
    logger.info("嵌入模块未安装: %s", e)

from core.registry import directive

DB_PATH: dict = {}
API_KEY_SERVICE = "bigmodel-embedding-3"


def init_embed_handler(db_path: str):
    global DB_PATH
    DB_PATH = {'config': db_path}


def _get_api_key() -> str:
    if not DB_PATH:
        return ''
    return key_get(DB_PATH, API_KEY_SERVICE) or ''


@directive("语义", "编码")
def sem_encode(params: list[str]) -> str:
    if not EMBED_ENABLED:
        return '嵌入模块未安装'

    if not params:
        return '参数不足: 语义;编码,<文本>[,模式]'

    api_key = _get_api_key()
    if not api_key:
        return f'密钥未配置: {API_KEY_SERVICE}。请先 指令:密钥;注册,{API_KEY_SERVICE},<key>,api_key'

    text = params[0]
    mode = params[1] if len(params) > 1 else 'B'
    try:
        vec = encode(text, api_key, mode)
        dims = len(vec)
        preview = [round(v, 6) for v in vec[:8]]
        return f'已编码 ({dims}维)\n预览: {preview}...'
    except Exception as e:
        return f'编码失败: {e}'


@directive("语义", "相似")
def sem_similarity(params: list[str]) -> str:
    if not EMBED_ENABLED:
        return '嵌入模块未安装'

    if len(params) < 2:
        return '参数不足: 语义;相似,<文本A>,<文本B>[,模式]'

    api_key = _get_api_key()
    if not api_key:
        return f'密钥未配置: {API_KEY_SERVICE}'

    a = params[0]
    b = params[1]
    mode = params[2] if len(params) > 2 else 'B'
    try:
        r = similarity(a, b, api_key, mode)
        return f"相似度: {r['score']*100:.1f}%\n判定: {r['verdict']}"
    except Exception as e:
        return f'语义相似失败: {e}'


@directive("语义", "匹配")
def sem_match(params: list[str]) -> str:
    if not EMBED_ENABLED:
        return '嵌入模块未安装'

    if len(params) < 2:
        return '参数不足: 语义;匹配,<查询>,<候选1>,<候选2>,...[,模式]'

    api_key = _get_api_key()
    if not api_key:
        return f'密钥未配置: {API_KEY_SERVICE}'

    query = params[0]
    # 最后一个如果是模式参数则去掉
    mode = 'B'
    candidates = list(params[1:])
    if candidates and candidates[-1].upper() in MODE_DIMS:
        mode = candidates.pop().upper()

    if not candidates:
        return '请提供至少一个候选项'

    try:
        r = match(query, candidates, api_key, mode)
        best = r['best']
        lines = [f"最佳匹配 ({best['score']*100:.1f}%): {best['text']}"]
        if len(r['ranking']) > 1:
            lines.append('')
            for i, item in enumerate(r['ranking']):
                lines.append(f"  {i+1}. [{item['score']*100:.1f}%] {item['text']}")
        return '\n'.join(lines)
    except Exception as e:
        return f'语义匹配失败: {e}'
