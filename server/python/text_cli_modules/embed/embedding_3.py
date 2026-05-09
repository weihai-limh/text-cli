"""
bigmodel/embedding-3 嵌入服务 — 纯 Python 在线版

依赖: urllib (Python stdlib)
边界: 不依赖 service/copilot/Worker 的任何模块
弹性: api_key 参数注入，零状态，纯函数

维度模式:
  A = 256, B = 512 (默认), C = 1024, D = 2048
"""

import json
import urllib.request
import urllib.error

API_URL = "https://open.bigmodel.cn/api/paas/v4/embeddings"
MODEL = "embedding-3"
DEFAULT_DIMS = 512

MODE_DIMS = {
    'A': 256,
    'B': 512,
    'C': 1024,
    'D': 2048,
}


def _resolve_dimensions(mode: str | int = 'B') -> int:
    if isinstance(mode, int):
        return mode
    return MODE_DIMS.get(mode.upper(), DEFAULT_DIMS)


def encode(text: str, api_key: str, dimensions: str | int = 'B') -> list[float]:
    """
    编码单段文本。
    返回: [float, ...] 维度由 dimensions 参数决定
    """
    dims = _resolve_dimensions(dimensions)
    body = json.dumps({
        "model": MODEL,
        "input": text,
        "dimensions": dims,
    }).encode('utf-8')

    req = urllib.request.Request(API_URL, data=body, headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    })

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        return data['data'][0]['embedding']
    except urllib.error.HTTPError as e:
        err = e.read().decode()[:200]
        raise RuntimeError(f"Embedding-3 API {e.code}: {err}")
    except Exception as e:
        raise RuntimeError(f"Embedding-3 调用失败: {e}")


def encode_batch(texts: list[str], api_key: str, dimensions: str | int = 'B') -> list[list[float]]:
    """
    批量编码（Embedding-3 原生支持数组输入）。
    返回: [[float, ...], ...]
    """
    dims = _resolve_dimensions(dimensions)
    body = json.dumps({
        "model": MODEL,
        "input": texts,
        "dimensions": dims,
    }).encode('utf-8')

    req = urllib.request.Request(API_URL, data=body, headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    })

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        return [item['embedding'] for item in data['data']]
    except urllib.error.HTTPError as e:
        err = e.read().decode()[:200]
        raise RuntimeError(f"Embedding-3 API {e.code}: {err}")
    except Exception as e:
        raise RuntimeError(f"Embedding-3 调用失败: {e}")


def _cosine(a: list[float], b: list[float]) -> float:
    n = min(len(a), len(b))
    dot = sum(a[i] * b[i] for i in range(n))
    na = sum(v * v for v in a)
    nb = sum(v * v for v in b)
    denom = (na ** 0.5) * (nb ** 0.5)
    return dot / denom if denom > 0 else 0.0


def similarity(a: str, b: str, api_key: str, dimensions: str | int = 'B') -> dict:
    """
    计算两段文本的语义相似度。
    返回: {'score': float, 'verdict': str, 'dimensions': int}
    """
    dims = _resolve_dimensions(dimensions)
    vecs = encode_batch([a, b], api_key, dims)
    score = _cosine(vecs[0], vecs[1])

    if score > 0.85:
        verdict = '高度相似 — 几乎在说同一件事'
    elif score > 0.7:
        verdict = '较强相似 — 语义方向一致'
    elif score > 0.5:
        verdict = '中度相似 — 有共同话题但观点可能不同'
    elif score > 0.3:
        verdict = '弱相关 — 只是话题领域临近'
    else:
        verdict = '不相关 — 语义差异很大'

    return {'score': round(score, 4), 'verdict': verdict, 'dimensions': dims}


def match(query: str, candidates: list[str], api_key: str, dimensions: str | int = 'B') -> dict:
    """
    从候选中找出语义最匹配的一项。
    返回: {'best': {'text': str, 'score': float}, 'ranking': [...]}
    """
    dims = _resolve_dimensions(dimensions)
    texts = [query] + candidates
    vecs = encode_batch(texts, api_key, dims)
    qv = vecs[0]

    ranking = [
        {'text': cand, 'score': round(_cosine(qv, vecs[i + 1]), 4)}
        for i, cand in enumerate(candidates)
    ]
    ranking.sort(key=lambda x: x['score'], reverse=True)

    return {
        'best': ranking[0],
        'ranking': ranking,
        'dimensions': dims,
    }
