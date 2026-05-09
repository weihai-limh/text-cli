"""
语义嵌入 — bigmodel/embedding-3

维度模式: A=256 / B=512(默认) / C=1024 / D=2048
依赖: urllib (stdlib only)
弹性: api_key 参数注入，零状态，纯函数
"""

import json
import urllib.request
import urllib.error

API_URL = "https://open.bigmodel.cn/api/paas/v4/embeddings"
MODEL = "embedding-3"

MODE_DIMS = {'A': 256, 'B': 512, 'C': 1024, 'D': 2048}


def _resolve_dimensions(mode='B'):
    return MODE_DIMS.get(str(mode).upper(), 512) if isinstance(mode, str) else mode


def encode(text, api_key, dimensions='B'):
    """编码单段文本。返回: [float, ...]"""
    dims = _resolve_dimensions(dimensions)
    body = json.dumps({"model": MODEL, "input": text, "dimensions": dims}).encode()
    req = urllib.request.Request(API_URL, data=body, headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        return data['data'][0]['embedding']
    except Exception as e:
        raise RuntimeError(f"Embedding-3: {e}")


def encode_batch(texts, api_key, dimensions='B'):
    """批量编码。返回: [[float, ...], ...]"""
    dims = _resolve_dimensions(dimensions)
    body = json.dumps({"model": MODEL, "input": texts, "dimensions": dims}).encode()
    req = urllib.request.Request(API_URL, data=body, headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    return [item['embedding'] for item in data['data']]


def _cosine(a, b):
    n = min(len(a), len(b))
    dot = sum(a[i] * b[i] for i in range(n))
    na = sum(v * v for v in a)
    nb = sum(v * v for v in b)
    return dot / ((na ** 0.5) * (nb ** 0.5)) if na and nb else 0.0


def similarity(a, b, api_key, dimensions='B'):
    """计算两段文本的语义相似度。"""
    dims = _resolve_dimensions(dimensions)
    vecs = encode_batch([a, b], api_key, dims)
    score = _cosine(vecs[0], vecs[1])
    if score > 0.85: v = '高度相似'
    elif score > 0.7: v = '较强相似'
    elif score > 0.5: v = '中度相似'
    elif score > 0.3: v = '弱相关'
    else: v = '不相关'
    return {'score': round(score, 4), 'verdict': v, 'dimensions': dims}


def match(query, candidates, api_key, dimensions='B'):
    """从候选中找出语义最匹配的一项。"""
    dims = _resolve_dimensions(dimensions)
    vecs = encode_batch([query] + candidates, api_key, dims)
    qv = vecs[0]
    ranking = [
        {'text': c, 'score': round(_cosine(qv, vecs[i+1]), 4)}
        for i, c in enumerate(candidates)
    ]
    ranking.sort(key=lambda x: x['score'], reverse=True)
    return {'best': ranking[0], 'ranking': ranking, 'dimensions': dims}
