import os
import time
import threading
import logging

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_post_timestamps: list[float] = []
_get_timestamps: list[float] = []

POST_LIMIT = int(os.getenv("RATE_LIMIT_PER_HOUR", "1000"))
GET_LIMIT = int(os.getenv("RATE_LIMIT_GET_PER_HOUR", "10000"))


def check_rate_limit(is_get: bool = False) -> bool:
    now = time.time()
    window = 3600.0
    limit = GET_LIMIT if is_get else POST_LIMIT
    timestamps = _get_timestamps if is_get else _post_timestamps

    with _lock:
        while timestamps and timestamps[0] < now - window:
            timestamps.pop(0)

        if len(timestamps) >= limit:
            logger.warning(
                "Rate limit exceeded: %s limit=%d count=%d",
                "GET" if is_get else "POST",
                limit,
                len(timestamps),
            )
            return False

        timestamps.append(now)
        return True
