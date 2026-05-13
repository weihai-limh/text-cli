"""
Key management handler — service edition

SQLite module available → handle locally
SQLite module unavailable → routed to copilot via proxy_routes.json (no handler registered)
"""

import logging

logger = logging.getLogger(__name__)

# Attempt to load SQLite
try:
    from text_cli_modules.key.key_registry import register as _reg
    from text_cli_modules.key.key_registry import revoke as _rev
    from text_cli_modules.key.key_registry import list_keys as _list
    SQLITE_ENABLED = True
    logger.info("SQLite key module loaded, local key management enabled")
except ImportError:
    SQLITE_ENABLED = False
    logger.info("SQLite module not installed, key directives forwarded via proxy")

DB_PATH: dict = {}


def init_key_handler(db_path: str):
    global DB_PATH
    DB_PATH = {'config': db_path}


# Only register directives when SQLite is available
if SQLITE_ENABLED:
    from core.registry import directive

    @directive("密钥", "注册")
    def key_register(params: list[str]) -> str:
        if len(params) < 3:
            return 'Missing params: key;register,service_name,key_value,key_type'
        svc, val, kt = params[0], params[1], params[2]
        r = _reg(DB_PATH, svc, val, kt)
        if r.get('ok'):
            return f'Key registered: {svc}'
        return f'Registration failed: {r.get("detail", r.get("error", "?"))}'

    @directive("密钥", "撤销")
    def key_revoke(params: list[str]) -> str:
        if not params:
            return 'Missing params: key;revoke,service_name'
        r = _rev(DB_PATH, params[0])
        if r.get('ok'):
            return f'Key revoked: {params[0]}'
        return f'Revocation failed: {r.get("detail", r.get("error", "?"))}'

    @directive("密钥", "列表")
    def key_list(params: list[str]) -> str:
        keys = _list(DB_PATH)
        if not keys:
            return 'Registered keys: (empty)'
        lines = [f'Registered keys: {len(keys)}']
        for k in keys:
            lines.append(f'  {k["service"]} ({k["key_type"]}) — {k["registered_at"]}')
        return '\n'.join(lines)
