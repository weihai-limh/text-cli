import os
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

# ── 配置 ────────────────────────────────────────
SERVICE_TOKEN = os.getenv("SERVICE_TOKEN", "")
A3_ALLOW_ANONYMOUS = os.getenv("A3_ALLOW_ANONYMOUS", "true").lower() == "true"
A3_COUNT_CALLS = os.getenv("A3_COUNT_CALLS", "false").lower() == "true"

# SQLite DB 路径（与 main.py 的 SQLITE_DB_FILE 一致，通过环境变量传入）
A6_DB_FILE = os.getenv("TEXT_CLI_SERVICE_DB", "")


@dataclass
class AuthResult:
    allowed: bool
    client_name: str
    identity_code: str   # token 后 6 位身份码。无 token 时为 ""
    message: str


def _resolve_identity(token: str | None) -> str:
    """
    提取身份码。

    优先级:
      1. X-Text-CLI-Identity header（由 A5 在转发时注入，目前通过函数参数传入）
         当前版本从 token 截取。A5 部署后调用方改为传入 header 值。
      2. Service-token 后 6 位（>=15 位时）
    """
    if token and len(token) >= 15:
        return token[-6:]
    return ""


def _check_token_registry(identity_code: str) -> tuple[bool, str]:
    """
    准入检查：查 token_registry 表。

    返回 (allowed, message)。
     - 表不存在 / 无记录 → allowed=True（向后兼容）
     - enabled=0 → allowed=False, TOKEN_DISABLED
     - 过期 → allowed=False, TOKEN_EXPIRED
    """
    if not identity_code or not A6_DB_FILE:
        return True, ""

    try:
        conn = sqlite3.connect(A6_DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT enabled, expires_at FROM token_registry WHERE token = ?",
            (identity_code,),
        )
        row = cursor.fetchone()
        conn.close()

        if row is None:
            return True, ""  # 无 token_registry 记录 → 放行

        enabled, expires_at = row
        if enabled == 0:
            return False, "TOKEN_DISABLED"

        if expires_at:
            try:
                exp_time = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                if datetime.utcnow() > exp_time.replace(tzinfo=None):
                    return False, "TOKEN_EXPIRED"
            except (ValueError, TypeError):
                pass  # 解析失败不阻断

        return True, ""
    except sqlite3.OperationalError:
        # 表不存在 → 放行（向后兼容：token_registry 还未建表）
        return True, ""
    except Exception as e:
        logger.warning("token_registry 查询失败: %s", e)
        return True, ""


def verify_service_token(token: str | None, identity_header: str | None = None) -> AuthResult:
    """
    验证 Service Token 并提取身份码。

    参数:
        token: Service-token header（完整 token）
        identity_header: X-Text-CLI-Identity header（A5 注入，当前未部署时为空）

    返回 AuthResult。
      - allowed=False → 中断请求
      - identity_code 非空 → handler 可用此身份查应用自建表
    """

    # ── ① 提取身份码 ──
    if identity_header:
        identity_code = identity_header
    else:
        identity_code = _resolve_identity(token)

    # ── ② 无 token 分支 ──
    if not identity_code:
        if A3_ALLOW_ANONYMOUS:
            return AuthResult(
                allowed=True,
                client_name="anonymous",
                identity_code="",
                message="",
            )
        else:
            return AuthResult(
                allowed=False,
                client_name="",
                identity_code="",
                message="Unauthorized: Service-token missing",
            )

    # ── ③ 准入检查 ──
    allowed, reason = _check_token_registry(identity_code)
    if not allowed:
        return AuthResult(
            allowed=False,
            client_name="",
            identity_code=identity_code,
            message=f"Unauthorized: {reason}",
        )

    # ── ④ 兼容旧 SERVICE_TOKEN 模式 ──
    # 如果配置了 SERVICE_TOKEN 环境变量，额外做 token 匹配校验
    if SERVICE_TOKEN:
        if not token or token.strip() != SERVICE_TOKEN:
            logger.warning("Service-token verification failed: prefix=%s",
                           token[:8] if token else "<none>")
            return AuthResult(
                allowed=False,
                client_name="",
                identity_code=identity_code,
                message="Unauthorized: Service-token invalid",
            )

    return AuthResult(
        allowed=True,
        client_name=identity_code,
        identity_code=identity_code,
        message="",
    )


def write_call_log(identity_code: str, domain: str, action: str,
                   status: str, error_msg: str = "", duration_ms: int = 0) -> None:
    """写入调用审计日志。仅在 A3_COUNT_CALLS=true 时写入。"""
    if not A3_COUNT_CALLS or not A6_DB_FILE:
        return

    log_token = identity_code if identity_code else "__anon__"
    try:
        conn = sqlite3.connect(A6_DB_FILE)
        conn.execute(
            """INSERT INTO token_call_logs (token, domain, action, status, error_msg, duration_ms)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (log_token, domain, action, status, error_msg or "", duration_ms),
        )
        conn.commit()
        conn.close()

        # 更新 used_count
        if identity_code and status == "ok":
            conn2 = sqlite3.connect(A6_DB_FILE)
            conn2.execute(
                "UPDATE token_registry SET used_count = used_count + 1 WHERE token = ?",
                (identity_code,),
            )
            conn2.commit()
            conn2.close()
    except Exception as e:
        logger.warning("token_call_logs 写入失败: %s", e)
