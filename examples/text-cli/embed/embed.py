"""
Semantic embedding — bigmodel/embedding-3

Dimension modes: A=256 / B=512(default) / C=1024 / D=2048
Dependency: urllib (stdlib only)
Resilient: api_key param injection, zero state, pure functions
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
    """Encode a single text. Returns: [float, ...]"""
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
    """Batch encode. Returns: [[float, ...], ...]"""
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
    """Compute semantic similarity between two texts."""
    dims = _resolve_dimensions(dimensions)
    vecs = encode_batch([a, b], api_key, dims)
    score = _cosine(vecs[0], vecs[1])
    if score > 0.85: v = 'highly similar'
    elif score > 0.7: v = 'strongly similar'
    elif score > 0.5: v = 'moderately similar'
    elif score > 0.3: v = 'weakly related'
    else: v = 'unrelated'
    return {'score': round(score, 4), 'verdict': v, 'dimensions': dims}


def match(query, candidates, api_key, dimensions='B'):
    """Find the best semantic match from candidates."""
    dims = _resolve_dimensions(dimensions)
    vecs = encode_batch([query] + candidates, api_key, dims)
    qv = vecs[0]
    ranking = [
        {'text': c, 'score': round(_cosine(qv, vecs[i+1]), 4)}
        for i, c in enumerate(candidates)
    ]
    ranking.sort(key=lambda x: x['score'], reverse=True)
    return {'best': ranking[0], 'ranking': ranking, 'dimensions': dims}
