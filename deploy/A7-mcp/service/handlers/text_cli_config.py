"""
text-cli;config — 平台自管理元指令：包配置热更新闸门（issues ISS-02）。

指令形态:
    AI:text-cli;config,<token>,<get|post>,<pkg>[,<json>]

闸门 = 开关 + token 校验 + 转发，零配置语义：不推断、不解析包配置文件
路径与 JSON 结构。包配置的读写与校验由包自行实现的 runtime_config(action,
payload) 钩子承担（见 package-python-dev-guide_zh.md 包侧钩子契约）。

闸门顺序:
    ① 开关未开启 → error: live-config is disabled, ...（先查开关、后验 token，
       关闭态不暴露 token 细节）
    ② token 缺失/不匹配 → error: invalid live-config token
       （token 独立于 auth.service_token，为内网匿名模式的二次防线）
    ③ 校验 <pkg> 已安装
    ④ 探测包 handler 的 runtime_config 钩子；未实现 → error: does not support
    ⑤ 转发 get/post，返回钩子结果（get/post 同构回显 {"status", "config"}，
       post 为写后读回显；错误走 reason）

配置来源: text_cli.yaml live_config 段（enabled / token），经 core.config 读取。

Author: Tide 🌊
"""

from __future__ import annotations

import json
import logging

from core.registry import directive

logger = logging.getLogger("text-cli.live_config")

_DISABLED_MSG = "live-config is disabled, please contact the administrator to enable it"
_INVALID_TOKEN_MSG = "invalid live-config token"
_USAGE_MSG = "Usage: AI:text-cli;config,<token>,<get|post>,<pkg>[,<json>]"


def _parse_json_params(params: list[str], start_idx: int) -> dict:
    """Parse JSON payload, tolerating comma-split reconstruction.

    The protocol parser splits params by comma, which can break JSON strings.
    Try direct parse first, then join remaining params with commas and retry.
    """
    if len(params) <= start_idx:
        raise ValueError("missing JSON parameter")

    direct = params[start_idx]
    try:
        return json.loads(direct)
    except json.JSONDecodeError:
        pass

    joined = ",".join(params[start_idx:])
    return json.loads(joined)


def _get_hook(pkg: str):
    """Return the package handler module's runtime_config hook, or None.

    Package handlers are imported at startup (handlers auto-discovery) and on
    install (_load_and_wire) — read from sys.modules first to avoid re-import.
    """
    import importlib
    import sys

    mod = sys.modules.get(f"packages.{pkg}.handler")
    if mod is None:
        try:
            mod = importlib.import_module(f"packages.{pkg}.handler")
        except Exception as e:
            logger.debug("live-config: cannot import handler for '%s': %s", pkg, e)
            return None
    hook = getattr(mod, "runtime_config", None)
    return hook if callable(hook) else None


@directive("text-cli", "config", domain_alias="文本指令", action_aliases={"config": "配置"})
def text_cli_config(params: list[str]) -> dict:
    """Live-config gate: get/post a package's config via its runtime_config hook."""
    # ① 开关（先查开关、后验 token —— 关闭态不暴露 token 细节）
    try:
        from core.config import load_config
        cfg = (load_config().get("live_config") or {})
    except Exception as e:
        logger.warning("live-config: load_config failed: %s", e)
        cfg = {}
    if not cfg.get("enabled", False):
        return {"status": "error", "reason": _DISABLED_MSG}

    # ② token 校验（独立于 auth.service_token 的二次防线）
    token_cfg = str(cfg.get("token", "") or "")
    supplied = params[0].strip() if params else ""
    if not token_cfg or not supplied or supplied != token_cfg:
        return {"status": "error", "reason": _INVALID_TOKEN_MSG}

    if len(params) < 3:
        return {"status": "error", "reason": _USAGE_MSG}

    action = params[1].strip().lower()
    if action not in ("get", "post"):
        return {"status": "error", "reason": f"invalid action '{params[1].strip()}': must be get or post"}

    pkg = params[2].strip()

    # ③ 已安装校验
    from .package_manifest import get as manifest_get
    if manifest_get(pkg) is None:
        return {"status": "error", "reason": f"package '{pkg}' is not installed"}

    # ④ 钩子探测
    hook = _get_hook(pkg)
    if hook is None:
        return {"status": "error",
                "reason": f"'{pkg}' does not support live-config "
                          f"(documented fallback: restart or install,<pkg>,--force after config changes)"}

    # ⑤ 转发
    payload = None
    if action == "post":
        try:
            payload = _parse_json_params(params, 3)
        except (json.JSONDecodeError, ValueError) as e:
            return {"status": "error", "reason": f"invalid JSON payload: {e}"}

    try:
        result = hook(action, payload)
    except Exception as e:
        logger.exception("live-config hook failed: pkg=%s action=%s", pkg, action)
        return {"status": "error", "reason": str(e)}

    if not isinstance(result, dict):
        # 契约：钩子返回 None = 不支持
        return {"status": "error",
                "reason": f"'{pkg}' does not support live-config action '{action}'"}
    return result
