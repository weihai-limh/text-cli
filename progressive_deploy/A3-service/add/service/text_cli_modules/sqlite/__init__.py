"""
text-cli-modules/sqlite — 纯基础设施：结构化 SQL 生成 + 自适应结果解析

不包含任何业务逻辑。key_registry 等业务模块在 text_cli_modules/key/ 下。
"""

from text_cli_modules.sqlite.database import init_db, get_sql_by_datas, post_sql_by_dbname

__all__ = [
    'init_db',
    'get_sql_by_datas',
    'post_sql_by_dbname',
]
