"""
text-cli-modules/key — 密钥管理业务模块

依赖: text_cli_modules.sqlite（基础设施）
边界: 不依赖任何 service/copilot 内部模块
弹性: db_path 外部注入，纯函数，零状态
"""

from text_cli_modules.key.key_registry import (
    get,
    get_all_keys,
    list_keys,
    register,
    revoke,
)

__all__ = [
    'get',
    'get_all_keys',
    'list_keys',
    'register',
    'revoke',
]
