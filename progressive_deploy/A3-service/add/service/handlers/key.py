"""
Key management handler — register, revoke, list, and export encrypted credentials.

Supports single and dual credentials, quota tracking integration, and XOR-encrypted
export for secure credential injection into external systems.

Dependencies: text_cli_modules/key/, text_cli_modules/sqlite/
"""

import json
import logging

logger = logging.getLogger(__name__)

try:
    from text_cli_modules.key.key_registry import register as _reg
    from text_cli_modules.key.key_registry import revoke as _rev
    from text_cli_modules.key.key_registry import list_keys as _list
    from text_cli_modules.key.key_registry import set_quota_track as _set_qt
    from text_cli_modules.key.key_registry import get_quota_track as _get_qt
    from text_cli_modules.key.key_registry import get_raw as _get_raw
    from text_cli_modules.key.key_registry import set_dispatch as _set_dispatch
    SQLITE_ENABLED = True
    logger.info("SQLite key module loaded, local key management enabled")
except ImportError:
    SQLITE_ENABLED = False
    logger.info("SQLite module not installed, key directives forwarded via proxy")

DB_PATH: dict = {}


def init_key_handler(db_path: str, dispatch_fn=None):
    global DB_PATH
    DB_PATH = {'config': db_path}
    if dispatch_fn and SQLITE_ENABLED:
        _set_dispatch(dispatch_fn)
        logger.info("key_registry: dispatch callback injected via init_key_handler")


if SQLITE_ENABLED:
    from core.registry import directive

    @directive("密钥", "注册")
    @directive("key", "register")
    def key_register(params: list[str]) -> str:
        if len(params) < 2:
            return 'Missing params: key;register,<service>,<value1>[,<value2>],<key_type>'

        service = params[0]
        key_type = params[-1]
        values = tuple(params[1:-1])

        if not values:
            return 'Missing key value(s)'

        r = _reg(DB_PATH, service, *values, key_type=key_type)
        if r.get('ok'):
            cc = r.get('cred_count', 1)
            return f'Key registered: {service} (type={key_type}, cred_count={cc})'
        return f'Registration failed: {r.get("detail", r.get("error", "?"))}'

    @directive("密钥", "撤销")
    @directive("key", "revoke")
    def key_revoke(params: list[str]) -> str:
        if not params:
            return 'Missing params: key;revoke,<service>'
        r = _rev(DB_PATH, params[0])
        if r.get('ok'):
            return f'Key revoked: {params[0]}'
        return f'Revocation failed: {r.get("detail", r.get("error", "?"))}'

    @directive("密钥", "列表")
    @directive("key", "list")
    def key_list(params: list[str]) -> str:
        keys = _list(DB_PATH)
        if not keys:
            return 'Registered keys: (empty)'
        lines = [f'Registered keys: {len(keys)}']
        for k in keys:
            cc = k.get('cred_count', 1)
            qt = k.get('quota_track')
            qt_str = f' [tracking: {",".join(qt)}]' if qt else ''
            lines.append(
                f'  {k["service"]} ({k["key_type"]}, '
                f'cred_count={cc}) — {k["registered_at"]}{qt_str}'
            )
        return '\n'.join(lines)

    @directive("key", "quota-track")
    @directive("密钥", "配额追踪")
    def key_quota_track(params: list[str]) -> str:
        if not params:
            return 'Missing params: key;quota-track,<service>[,<target1>,...]'

        service = params[0]
        targets = params[1:] if len(params) > 1 else None

        r = _set_qt(DB_PATH, service, targets)
        if r.get('ok'):
            if targets:
                return f'Quota tracking set for {service}: {", ".join(targets)}'
            return f'Quota tracking cleared for {service}'
        return f'Failed: {r.get("detail", r.get("error", "?"))}'

    @directive("key", "export-xor")
    @directive("密钥", "导出加密")
    def key_export_xor(params: list[str]) -> str:
        if not params:
            return 'Missing params: key;export-xor,<service>'

        service = params[0]

        raw = _get_raw(DB_PATH, service)
        if not raw:
            return f'Key not found: {service}'

        value = raw.get('value', '')
        if not value:
            return f'Key {service} has no value'

        var_name = f'XOR_KEY_{service.replace("-", "_")}'
        xor_secret = __import__('os').environ.get(var_name, '')
        if not xor_secret:
            return f'XOR key not configured: set env var {var_name}'

        cipher = _xor_encrypt(value, xor_secret)
        cred_count = raw.get('cred_count', 1)

        logger.info(
            'key;export-xor: service=%s cred_count=%d len=%d',
            service, cred_count, len(cipher)
        )

        if cred_count == 1:
            return f'export-xor:{service}\ncipher: {cipher}'
        else:
            value2 = raw.get('value2', '')
            if value2:
                cipher2 = _xor_encrypt(value2, xor_secret)
                return f'export-xor:{service}\ncipher1: {cipher}\ncipher2: {cipher2}'
            return f'export-xor:{service}\ncipher: {cipher}'


def _xor_encrypt(plaintext: str, xor_secret: str) -> str:
    key_bytes = xor_secret.encode('utf-8')
    plain_bytes = plaintext.encode('utf-8')
    cipher = bytes(p ^ key_bytes[i % len(key_bytes)] for i, p in enumerate(plain_bytes))
    return cipher.hex()
