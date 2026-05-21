import os
import hashlib
import time
import logging
from core.database import query_db, execute_db

logger = logging.getLogger(__name__)

_registered_prefixes = None
_blocked_prefixes = None


def _load_st_prefixes():
    global _registered_prefixes, _blocked_prefixes
    raw_reg = os.getenv("A3_REGISTERED_PREFIXES", "")
    _registered_prefixes = set(p.strip() for p in raw_reg.split(",") if p.strip())
    raw_blk = os.getenv("ST_PREFIX_BLACKLIST", "")
    _blocked_prefixes = set(p.strip() for p in raw_blk.split(",") if p.strip())


def update_registered_prefixes(prefixes: set[str]):
    global _registered_prefixes
    _registered_prefixes = prefixes


def is_st_prefix_blocked(prefix: str) -> bool:
    if _blocked_prefixes is None:
        _load_st_prefixes()
    return prefix in _blocked_prefixes


def is_st_prefix_registered(prefix: str) -> bool:
    if _registered_prefixes is None:
        _load_st_prefixes()
    if not _registered_prefixes:
        return True
    return prefix in _registered_prefixes

_token_bucket: dict[str, list[float]] = {}


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_access_token(token: str | None, required: bool = True) -> dict | None:
    if not required:
        return None

    if not token:
        return None

    clean = token
    if clean.startswith("Bearer "):
        clean = clean[7:]
    clean = clean.strip()

    if not clean:
        return None

    token_hash = hash_token(clean)

    rows = query_db(
        "SELECT * FROM access_tokens WHERE token_hash = ? AND is_active = 1",
        (token_hash,),
    )

    if not rows:
        logger.warning("Token verification failed: hash prefix=%s", token_hash[:8])
        return None

    record = rows[0]

    if record["quota"] >= 0 and record["used_count"] >= record["quota"]:
        logger.warning("Token quota exceeded: prefix=%s, used=%d, quota=%d",
                        record["token_prefix"], record["used_count"], record["quota"])
        return None

    if not _check_rate_limit(record["token_hash"], record["max_requests_per_minute"]):
        logger.warning("Rate limit exceeded: prefix=%s", record["token_prefix"])
        return None

    return record


def _check_rate_limit(token_hash: str, max_rpm: int) -> bool:
    now = time.time()
    window = 60.0

    if token_hash not in _token_bucket:
        _token_bucket[token_hash] = []

    timestamps = _token_bucket[token_hash]

    while timestamps and timestamps[0] < now - window:
        timestamps.pop(0)

    if len(timestamps) >= max_rpm:
        return False

    timestamps.append(now)
    return True


def increment_token_usage(token_prefix: str):
    execute_db(
        "UPDATE access_tokens SET used_count = used_count + 1 WHERE token_prefix = ?",
        (token_prefix,),
    )


def extract_token_prefix(token: str | None) -> str:
    if not token:
        return ""
    clean = token
    if clean.startswith("Bearer "):
        clean = clean[7:]
    clean = clean.strip()
    return clean[:8] if len(clean) >= 8 else clean


def extract_service_token_prefix(service_token: str | None) -> str:
    if not service_token:
        return ""
    return service_token[:8] if len(service_token) >= 8 else service_token
