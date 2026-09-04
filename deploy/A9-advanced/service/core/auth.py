import logging
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ── 配置 ────────────────────────────────────────
# 唯一配置入口：text_cli.yaml auth 段（经 core.config.load_config() 统一读取，
# env 覆盖（SERVICE_TOKEN / A3_ALLOW_ANONYMOUS / A3_COUNT_CALLS）由 config.py
# 的 _ENV_OVERRIDES 提供，优先级 env > yaml > 默认）。下方模块级常量仅为
# load_config() 不可用时的兜底缺省。
# 生效时机：启动快照——首次调用 _auth_snapshot() 时加载并缓存，进程内不热更
# （框架配置热更归 live-config 范畴，见 issues ISS-02）。
SERVICE_TOKEN = os.getenv("SERVICE_TOKEN", "")
A3_ALLOW_ANONYMOUS = os.getenv("A3_ALLOW_ANONYMOUS", "true").lower() == "true"
A3_COUNT_CALLS = os.getenv("A3_COUNT_CALLS", "false").lower() == "true"

_AUTH_SNAPSHOT: dict | None = None


def _auth_snapshot() -> dict:
    """Startup snapshot of the auth config section (loaded once, no hot reload)."""
    global _AUTH_SNAPSHOT
    if _AUTH_SNAPSHOT is None:
        cfg: dict = {}
        try:
            from core.config import load_config
            cfg = load_config().get("auth") or {}
        except Exception as e:  # defensive: config loader unavailable → env defaults
            logger.warning("load_config() unavailable, auth falls back to env defaults: %s", e)
        _AUTH_SNAPSHOT = {
            "service_token": str(cfg.get("service_token", SERVICE_TOKEN) or ""),
            "allow_anonymous": bool(cfg.get("allow_anonymous", A3_ALLOW_ANONYMOUS)),
            "count_calls": bool(cfg.get("count_calls", A3_COUNT_CALLS)),
        }
    return _AUTH_SNAPSHOT

# SQLite DB 路径（与 main.py 的 SQLITE_DB_FILE 一致，通过环境变量传入）
import pathlib as _pl

A6_DB_FILE = os.getenv(
    "TEXT_CLI_SERVICE_DB",
    str(_pl.Path(__file__).resolve().parent.parent / "text_cli_modules" / "sqlite" / "service.db")
)


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
                if datetime.now(timezone.utc) > exp_time.replace(tzinfo=None):
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

    配置语义（text_cli.yaml auth 段，启动快照）:
      - service_token 非空 → 强制模式：所有请求必须携带且匹配 Service-token，
        缺失/不匹配一律拒绝（不落 allow_anonymous 匿名分支）；匹配后先取身份码
        （A5 header 优先，其次 token 尾 6 位），再做 registry 准入。
      - service_token 为空 → 原流程：提取身份码；无身份码时由 allow_anonymous
        决定匿名放行 / 拒绝；有身份码则做 registry 准入。

    参数:
        token: Service-token header（完整 token）
        identity_header: X-Text-CLI-Identity header（A5 注入，优先于 token 尾码）

    返回 AuthResult。
      - allowed=False → 中断请求
      - identity_code 非空 → handler 可用此身份查应用自建表
    """
    cfg = _auth_snapshot()
    service_token = cfg["service_token"]

    # ── 强制模式：service_token 非空 → 所有请求必须携带且匹配（先匹配、后准入）──
    if service_token:
        if not token or token.strip() != service_token:
            logger.warning("Service-token verification failed: prefix=%s",
                           token[:8] if token else "<none>")
            return AuthResult(
                allowed=False,
                client_name="",
                identity_code="",
                message="Unauthorized: Service-token invalid",
            )
        identity_code = identity_header or _resolve_identity(token)
        if not identity_code:
            # 匹配 token 但取不到身份码（如 token 长度 <15 且无 A5 header）：
            # 强制模式下不存在匿名分支 → 拒绝
            return AuthResult(
                allowed=False,
                client_name="",
                identity_code="",
                message="Unauthorized: Service-token missing",
            )
        allowed, reason = _check_token_registry(identity_code)
        if not allowed:
            return AuthResult(
                allowed=False,
                client_name="",
                identity_code=identity_code,
                message=f"Unauthorized: {reason}",
            )
        return AuthResult(
            allowed=True,
            client_name=identity_code,
            identity_code=identity_code,
            message="",
        )

    # ── 原流程：service_token 为空 → 提取身份码 → registry 准入 → 匿名策略 ──
    identity_code = identity_header or _resolve_identity(token)

    # ── 无身份码分支 ──
    if not identity_code:
        if cfg["allow_anonymous"]:
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

    # ── 准入检查 ──
    allowed, reason = _check_token_registry(identity_code)
    if not allowed:
        return AuthResult(
            allowed=False,
            client_name="",
            identity_code=identity_code,
            message=f"Unauthorized: {reason}",
        )

    return AuthResult(
        allowed=True,
        client_name=identity_code,
        identity_code=identity_code,
        message="",
    )


def write_call_log(identity_code: str, domain: str, action: str,
                   status: str, error_msg: str = "", duration_ms: int = 0) -> None:
    """写入调用审计日志。仅在 auth.count_calls=true 时写入（启动快照）。"""
    if not _auth_snapshot()["count_calls"] or not A6_DB_FILE:
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
