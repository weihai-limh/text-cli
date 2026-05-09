"""
SQLite 薄封装 — 结构化 SQL 生成 + 自适应结果解析
纯函数，零外部依赖，db_path 外部注入

设计思想：
  - 不 import 任何项目模块
  - 不持有连接状态（每次调用 connect → 执行 → close）
  - get_sql_by_datas 返回 SQL 字符串，可与任何执行器组合
  - post_sql_by_dbname 自动适配返回值形状（单值/list/dict）

来源：lemondy 的设计模式
"""

import sqlite3


def post_sql_by_dbname(db_path: dict, sql: str):
    """
    执行 SQL，自适应结果解析。
    
    db_path: {'config': '/path/to/db', 'logs': '/path/to/logs.db'}
    返回:
      - SELECT 单值: 值本身
      - SELECT 单列多行: list
      - SELECT 多列: dict {col0: [col1, col2, ...]}
      - INSERT/UPDATE/DELETE: 执行结果
    """
    # 从 db_path dict 中找匹配的数据库
    # name 参数可以是 key 也可以是通配——这里简化为取第一个
    db_file = list(db_path.values())[0] if isinstance(db_path, dict) else db_path

    if isinstance(db_path, dict):
        # 尝试按 name 匹配
        pass  # 简化处理，直接用第一个

    rst_list = []
    rst_dict = {}
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    if 'SELECT' in sql.upper():
        cursor.execute(sql)
        rows = cursor.fetchall()
        for i in rows:
            if len(i) > 1:
                rst_dict.update({i[0]: [z for z in i[1:]]})
            else:
                if isinstance(i[0], str):
                    if ',' in i[0]:
                        rst_list.append(i[0].split(','))
                    else:
                        rst_list.append(i[0])
                else:
                    rst_list.append(i[0])
        if len(rst_list) > len(rst_dict):
            rst = rst_list
        else:
            rst = rst_dict
    else:
        rst = cursor.execute(sql)
        conn.commit()

    conn.close()
    return rst


def get_sql_by_datas(types: str, datas: dict) -> str:
    """
    将 dict 描述的结构化查询意图转换为 SQL 字符串。
    
    types: 'q'(query) / 'in'(insert) / 'up'(update) / 'del'(delete)
    
    datas 结构:
    {
        'table_name': 'key_registry',
        'q_str': 'value,key_type',           # SELECT 列
        'where1': ['service', 'smtp-tide'],  # WHERE 条件
        'in_data': {'service': '...', 'value': '...'},  # INSERT 数据
        'up_list1': ['value', 'new_value'],  # UPDATE SET
    }
    """
    if 'where1' in datas:
        where_part = f" WHERE {datas['where1'][0]} ='{datas['where1'][1]}'"
    else:
        where_part = ''

    if 'q_str' in datas:
        q_obj_part = datas['q_str']
    else:
        q_obj_part = '*'

    if 'in_data' in datas:
        data_k = ','.join(list(datas["in_data"].keys()))
        data_v = "','".join(list(datas["in_data"].values()))

    if 'up_list1' in datas:
        set_part = f" SET {datas['up_list1'][0]} ='{datas['up_list1'][1]}'"

    if types == 'q':
        sql = f"SELECT {q_obj_part} FROM {datas['table_name']}{where_part}"
    elif types == 'up' and 'up_list1' in datas:
        sql = f"UPDATE {datas['table_name']} {set_part} {where_part}"
    elif types == 'in' and 'in_data' in datas:
        sql = f"INSERT INTO {datas['table_name']} ({data_k}) VALUES ('{data_v}')"
    elif types == 'del' and 'where1' in datas:
        sql = f"DELETE FROM {datas['table_name']}{where_part}"
    else:
        raise ValueError(f"不支持的查询类型或缺少参数: types={types}, keys={list(datas.keys())}")

    return sql


def init_db(db_path: str) -> None:
    """初始化 SQLite 数据库和表结构"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS key_registry (
            service TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            key_type TEXT NOT NULL,
            registered_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # 调用日志表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS call_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL DEFAULT (datetime('now')),
            action TEXT NOT NULL,
            service TEXT,
            detail TEXT
        )
    """)

    conn.commit()
    conn.close()
