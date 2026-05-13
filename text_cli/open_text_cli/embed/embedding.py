"""
BigModel / Embedding-3 embedding service — pure Python, online edition.

Dependencies: urllib (Python stdlib)
Boundary: independent of service/copilot/Worker modules
Resilience: api_key injected as parameter, stateless, pure functions

Dimension modes:
  A = 256, B = 512 (default), C = 1024, D = 2048
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
    Encode a single text segment.
    Returns: [float, ...] with dimensionality determined by dimensions param.
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
        raise RuntimeError(f"Embedding-3 call failed: {e}")


def encode_batch(texts: list[str], api_key: str, dimensions: str | int = 'B') -> list[list[float]]:
    """
    Batch encoding (Embedding-3 natively supports array input).
    Returns: [[float, ...], ...]
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
        raise RuntimeError(f"Embedding-3 call failed: {e}")


def _cosine(a: list[float], b: list[float]) -> float:
    n = min(len(a), len(b))
    dot = sum(a[i] * b[i] for i in range(n))
    na = sum(v * v for v in a)
    nb = sum(v * v for v in b)
    denom = (na ** 0.5) * (nb ** 0.5)
    return dot / denom if denom > 0 else 0.0


def similarity(a: str, b: str, api_key: str, dimensions: str | int = 'B') -> dict:
    """
    Compute semantic similarity between two text segments.
    Returns: {'score': float, 'verdict': str, 'dimensions': int}
    """
    dims = _resolve_dimensions(dimensions)
    vecs = encode_batch([a, b], api_key, dims)
    score = _cosine(vecs[0], vecs[1])

    if score > 0.85:
        verdict = 'Highly similar — nearly the same meaning'
    elif score > 0.7:
        verdict = 'Strongly similar — aligned semantic direction'
    elif score > 0.5:
        verdict = 'Moderately similar — shared topic, possibly different views'
    elif score > 0.3:
        verdict = 'Weakly related — adjacent topic domains only'
    else:
        verdict = 'Unrelated — large semantic divergence'

    return {'score': round(score, 4), 'verdict': verdict, 'dimensions': dims}


def match(query: str, candidates: list[str], api_key: str, dimensions: str | int = 'B') -> dict:
    """
    Find the semantically closest match from a list of candidates.
    Returns: {'best': {'text': str, 'score': float}, 'ranking': [...]}
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
