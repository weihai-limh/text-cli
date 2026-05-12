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


def verify_service_token(token: str | None) -> AuthResult:
    if not SERVICE_TOKEN:
        return AuthResult(allowed=True, client_name="anonymous", message="")

    if not token:
        return AuthResult(
            allowed=False,
            client_name="",
            message="无权访问：Service-token 缺失",
        )

    clean = token.strip()

    if clean != SERVICE_TOKEN:
        logger.warning("Service-token 验证失败: prefix=%s", clean[:8])
        return AuthResult(
            allowed=False,
            client_name="",
            message="无权访问：Service-token 无效",
        )

    return AuthResult(allowed=True, client_name="authenticated", message="")
