import os
import time
import uuid
import logging
import httpx
from dataclasses import dataclass
from core.database import execute_db, query_db
from core.parser import ParsedDirective

logger = logging.getLogger(__name__)

FORWARD_TIMEOUT = float(os.getenv("FORWARD_TIMEOUT", "30"))
MAX_RETRIES = int(os.getenv("FORWARD_MAX_RETRIES", "1"))


@dataclass
class ForwardResult:
    status_code: int
    body: bytes
    headers: dict
    response_time_ms: int
    error_message: str | None = None


async def forward_request(
    parsed: ParsedDirective,
    backend_url: str,
    prompt: str,
    access_token: str | None,
    service_token: str | None,
) -> ForwardResult:
    request_id = str(uuid.uuid4())
    headers = {
        "Content-Type": "application/json",
    }

    if service_token:
        headers["Service-token"] = service_token

    body = {"prompt": prompt}

    last_error = None
    result = None

    for attempt in range(1 + MAX_RETRIES):
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=FORWARD_TIMEOUT) as client:
                resp = await client.post(backend_url, json=body, headers=headers)
                elapsed = int((time.monotonic() - start) * 1000)

                result = ForwardResult(
                    status_code=resp.status_code,
                    body=resp.content,
                    headers=dict(resp.headers),
                    response_time_ms=elapsed,
                )

                if resp.status_code >= 500 and attempt < MAX_RETRIES:
                    logger.warning("Backend 5xx (attempt %d/%d): %d from %s",
                                   attempt + 1, 1 + MAX_RETRIES, resp.status_code, backend_url)
                    last_error = f"5xx {resp.status_code}"
                    continue

                break

        except httpx.TimeoutException:
            elapsed = int((time.monotonic() - start) * 1000)
            last_error = "timeout"
            logger.warning("Backend timeout (attempt %d/%d) after %dms: %s",
                           attempt + 1, 1 + MAX_RETRIES, elapsed, backend_url)
            result = ForwardResult(
                status_code=408,
                body=b'{"rst_types":"text","rst_data":{"text":"request to backend timed out"}}',
                headers={"Content-Type": "application/json"},
                response_time_ms=elapsed,
                error_message="timeout",
            )
            if attempt < MAX_RETRIES:
                continue
            break

        except httpx.RequestError as e:
            elapsed = int((time.monotonic() - start) * 1000)
            last_error = str(e)
            logger.error("Backend request error (attempt %d/%d): %s",
                         attempt + 1, 1 + MAX_RETRIES, e)
            result = ForwardResult(
                status_code=502,
                body=b'{"rst_types":"text","rst_data":{"text":"backend request failed"}}',
                headers={"Content-Type": "application/json"},
                response_time_ms=elapsed,
                error_message=str(e),
            )
            if attempt < MAX_RETRIES:
                continue
            break

    log_call(
        request_id=request_id,
        directive=parsed.raw,
        domain=parsed.domain,
        action=parsed.action,
        backend_url=backend_url,
        service_token_prefix=(service_token[:8] + "***") if service_token and len(service_token) > 8 else "",
        access_token_prefix=(access_token[:8] if access_token and len(access_token) >= 8 else (access_token or "")),
        status_code=result.status_code if result else 0,
        response_time_ms=result.response_time_ms if result else 0,
        error_message=result.error_message if result else last_error,
    )

    update_daily_stats(parsed.domain, parsed.action, result.status_code if result else 0, result.response_time_ms if result else 0)

    return result


def log_call(request_id, directive, domain, action, backend_url,
             service_token_prefix, access_token_prefix,
             status_code, response_time_ms, error_message):
    execute_db(
        """INSERT INTO call_logs
           (request_id, directive, domain, action, backend_url,
            service_token_prefix, access_token_prefix,
            status_code, response_time_ms, error_message)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (request_id, directive, domain, action, backend_url,
         service_token_prefix, access_token_prefix,
         status_code, response_time_ms, error_message),
    )


def update_daily_stats(domain, action, status_code, response_time_ms):
    from datetime import datetime
    today = datetime.utcnow().strftime("%Y-%m-%d")
    is_success = 1 if status_code == 200 else 0

    existing = query_db(
        "SELECT id, call_count, success_count, avg_response_ms FROM daily_stats WHERE date=? AND domain=? AND action=?",
        (today, domain, action),
    )

    if existing:
        row = existing[0]
        new_count = row["call_count"] + 1
        new_success = row["success_count"] + is_success
        new_avg = int((row["avg_response_ms"] * row["call_count"] + response_time_ms) / new_count)
        execute_db(
            "UPDATE daily_stats SET call_count=?, success_count=?, avg_response_ms=? WHERE id=?",
            (new_count, new_success, new_avg, row["id"]),
        )
    else:
        execute_db(
            "INSERT INTO daily_stats (date, domain, action, call_count, success_count, avg_response_ms) VALUES (?,?,?,?,?,?)",
            (today, domain, action, 1, is_success, response_time_ms),
        )
