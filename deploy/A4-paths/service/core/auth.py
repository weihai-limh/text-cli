import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_config_cache: dict | None = None


def _get_auth_config() -> dict:
    """Lazy-load auth config section. Falls back to env vars if YAML not available."""
    global _config_cache
    if _config_cache is not None:
        return _config_cache

    try:
        from core.config import load_config
        _config_cache = load_config().get("auth", {})
    except Exception:
        _config_cache = {}

    # Env var fallback (backward compatible)
    if "service_token" not in _config_cache or not _config_cache.get("service_token"):
        _config_cache["service_token"] = os.getenv("SERVICE_TOKEN", "")
    if "allow_anonymous" not in _config_cache:
        _config_cache["allow_anonymous"] = os.getenv("A3_ALLOW_ANONYMOUS", "true").lower() == "true"
    if "count_calls" not in _config_cache:
        _config_cache["count_calls"] = os.getenv("A3_COUNT_CALLS", "false").lower() == "true"

    return _config_cache


@dataclass
class AuthResult:
    allowed: bool
    client_name: str
    message: str
    identity_code: str = ""


def verify_service_token(token: str | None) -> AuthResult:
    def _resolve_identity(tok: str | None) -> str:
        if not tok:
            return ""
        clean = tok.strip()
        return clean[-6:] if len(clean) >= 6 else clean

    auth = _get_auth_config()
    service_token = auth.get("service_token", "")
    identity_code = _resolve_identity(token)

    if not service_token:
        return AuthResult(allowed=True, client_name="anonymous", message="",
                         identity_code=identity_code)

    if not token:
        return AuthResult(
            allowed=False,
            client_name="",
            message="Unauthorized: Service-token missing",
            identity_code=identity_code,
        )

    clean = token.strip()

    if clean != service_token:
        logger.warning("Service-token verification failed: prefix=%s", clean[:8])
        return AuthResult(
            allowed=False,
            client_name="",
            message="Unauthorized: Service-token invalid",
            identity_code=identity_code,
        )

    return AuthResult(allowed=True, client_name="authenticated", message="",
                     identity_code=identity_code)
