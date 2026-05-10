"""
密钥管理 handler — service 版

SQLite 模块存在 → 本地处理
SQLite 模块不存在 → 由 proxy_routes.json 路由到 copilot（不注册任何 handler）
"""

import logging

logger = logging.getLogger(__name__)

# 尝试加载 SQLite
try:
    from text_cli_modules.key.key_registry import register as _reg
    from text_cli_modules.key.key_registry import revoke as _rev
    from text_cli_modules.key.key_registry import list_keys as _list
    SQLITE_ENABLED = True
    logger.info("SQLite 密钥模块已加载，启用本地密钥管理")
except ImportError:
    SQLITE_ENABLED = False
    logger.info("SQLite 模块未安装，密钥指令由 proxy 转发")

DB_PATH: dict = {}


def init_key_handler(db_path: str):
    global DB_PATH
    DB_PATH = {'config': db_path}


# 只在 SQLite 可用时注册指令
if SQLITE_ENABLED:
    from core.registry import directive

    @directive("密钥", "注册")
    def key_register(params: list[str]) -> str:
        if len(params) < 3:
            return '参数不足: 密钥;注册,服务名,密钥值,密钥类型'
        svc, val, kt = params[0], params[1], params[2]
        r = _reg(DB_PATH, svc, val, kt)
        if r.get('ok'):
            return f'密钥已注册: {svc}'
        return f'注册失败: {r.get("detail", r.get("error", "?"))}'

    @directive("密钥", "撤销")
    def key_revoke(params: list[str]) -> str:
        if not params:
            return '参数不足: 密钥;撤销,服务名'
        r = _rev(DB_PATH, params[0])
        if r.get('ok'):
            return f'密钥已撤销: {params[0]}'
        return f'撤销失败: {r.get("detail", r.get("error", "?"))}'

    @directive("密钥", "列表")
    def key_list(params: list[str]) -> str:
        keys = _list(DB_PATH)
        if not keys:
            return '已注册密钥: (空)'
        lines = [f'已注册密钥: {len(keys)} 个']
        for k in keys:
            lines.append(f'  {k["service"]} ({k["key_type"]}) — {k["registered_at"]}')
        return '\n'.join(lines)
