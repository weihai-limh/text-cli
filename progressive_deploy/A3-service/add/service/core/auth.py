import os
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

SERVICE_TOKEN = os.getenv("SERVICE_TOKEN", "")


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

    identity_code = _resolve_identity(token)
    if not SERVICE_TOKEN:
        return AuthResult(allowed=True, client_name="anonymous", message="", identity_code=identity_code)

    if not token:
        return AuthResult(
            allowed=False,
            client_name="",
            message="Unauthorized: Service-token missing",
            identity_code=identity_code,
        )

    clean = token.strip()

    if clean != SERVICE_TOKEN:
        logger.warning("Service-token verification failed: prefix=%s", clean[:8])
        return AuthResult(
            allowed=False,
            client_name="",
            message="Unauthorized: Service-token invalid",
            identity_code=identity_code,
        )

    return AuthResult(allowed=True, client_name="authenticated", message="", identity_code=identity_code)
