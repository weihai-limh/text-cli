"""
Key management handler — service edition v2

v2 新增:
  - 双凭据注册 (key;register,svc,val1[,val2],type)
  - 配额追踪指令 (key;quota-track,svc[,target1,target2,...])
  - dispatch 回调注入 (key_registry.set_dispatch)

SQLite module available → handle locally
SQLite module unavailable → routed to copilot via proxy_routes.json (no handler registered)
"""

import logging

logger = logging.getLogger(__name__)

try:
    from text_cli_modules.key.key_registry import get_quota_track as _get_qt
    from text_cli_modules.key.key_registry import list_keys as _list
    from text_cli_modules.key.key_registry import register as _reg
    from text_cli_modules.key.key_registry import revoke as _rev
    from text_cli_modules.key.key_registry import set_dispatch as _set_dispatch
    from text_cli_modules.key.key_registry import set_quota_track as _set_qt
    SQLITE_ENABLED = True
    logger.info("SQLite key module loaded, local key management enabled")
except ImportError:
    SQLITE_ENABLED = False
    logger.info("SQLite module not installed, key directives forwarded via proxy")

DB_PATH: dict = {}


def init_key_handler(db_path: str, dispatch_fn=None):
    """Initialise key handler with SQLite DB path and optional dispatch callback."""
    global DB_PATH
    DB_PATH = {'config': db_path}
    if dispatch_fn and SQLITE_ENABLED:
        _set_dispatch(dispatch_fn)
        logger.info("key_registry: dispatch callback injected via init_key_handler")


if SQLITE_ENABLED:
    from core.registry import directive

    @directive("key", "register", domain_alias="密钥", action_aliases={"register": "注册"})
    def key_register(params: list[str]) -> dict:
        """
        key;register,<service>,<value1>[,<value2>],<key_type>

        单凭据: key;register,zhipu,xxx,api_key
        双凭据: key;register,tx,secret_id,secret_key,tencent_cloud
        """
        if len(params) < 2:
            return {"status": "error", "reason": "Missing params: key;register,<service>,<value1>[,<value2>],<key_type>"}

        service = params[0]
        key_type = params[-1]  # last param is always key_type
        values = tuple(params[1:-1])  # everything between service and key_type

        if not values:
            return {"status": "error", "reason": "Missing key value(s)"}

        r = _reg(DB_PATH, service, *values, key_type=key_type)
        if r.get('ok'):
            cc = r.get('cred_count', 1)
            return {"status": "ok", "service": service, "key_type": key_type, "cred_count": cc}
        return {"status": "error", "reason": f"Registration failed: {r.get('detail', r.get('error', '?'))}"}

    @directive("key", "revoke", domain_alias="密钥", action_aliases={"revoke": "撤销"})
    def key_revoke(params: list[str]) -> dict:
        if not params:
            return {"status": "error", "reason": "Missing params: key;revoke,<service>"}
        r = _rev(DB_PATH, params[0])
        if r.get('ok'):
            return {"status": "ok", "service": params[0]}
        return {"status": "error", "reason": f"Revocation failed: {r.get('detail', r.get('error', '?'))}"}

    @directive("key", "list", domain_alias="密钥", action_aliases={"list": "列表"})
    def key_list(params: list[str]) -> dict:
        keys = _list(DB_PATH)
        if not keys:
            return {"status": "ok", "keys": []}
        return {"status": "ok", "keys": keys}

    @directive("key", "quota-track", domain_alias="密钥", action_aliases={"quota-track": "配额追踪"})
    def key_quota_track(params: list[str]) -> dict:
        """
        key;quota-track,<service>[,<target1>,<target2>,...]

        设置: key;quota-track,zhipu,AI:inference,AI:vision
        清除: key;quota-track,zhipu
        """
        if not params:
            return {"status": "error", "reason": "Missing params: key;quota-track,<service>[,<target1>,...]"}

        service = params[0]
        targets = params[1:] if len(params) > 1 else None

        r = _set_qt(DB_PATH, service, targets)
        if r.get('ok'):
            if targets:
                return {"status": "ok", "service": service, "targets": targets}
            return {"status": "ok", "service": service, "targets": None}
        return {"status": "error", "reason": f"Failed: {r.get('detail', r.get('error', '?'))}"}
