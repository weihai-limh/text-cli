"""跨 handler 共享的身份上下文。"""
import contextvars

_IDENTITY_CTX = contextvars.ContextVar('identity_code', default='')


def set_identity(identity_code: str) -> None:
    _IDENTITY_CTX.set(identity_code)


def get_identity() -> str:
    return _IDENTITY_CTX.get() or ""
