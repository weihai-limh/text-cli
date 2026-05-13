"""
SQLite thin wrapper — structured SQL generation + adaptive result parsing.
Pure functions, zero external dependencies, db_path injected externally.

Design principles:
  - No imports from any project modules
  - No persistent connection state (connect → execute → close per call)
  - get_sql_by_datas returns SQL string, composable with any executor
  - post_sql_by_dbname auto-adapts return shape (single value / list / dict)

Origin: lemondy's design pattern
"""

import sqlite3


def post_sql_by_dbname(db_path: dict, sql: str):
    """
    Execute SQL, adaptive result parsing.

    db_path: {'config': '/path/to/db', 'logs': '/path/to/logs.db'}
    Returns:
      - SELECT single value: the value itself
      - SELECT single column, multiple rows: list
      - SELECT multiple columns: dict {col0: [col1, col2, ...]}
      - INSERT/UPDATE/DELETE: execution result
    """
    db_file = list(db_path.values())[0] if isinstance(db_path, dict) else db_path

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
    Convert a dict-described structured query intent into an SQL string.

    types: 'q'(query) / 'in'(insert) / 'up'(update) / 'del'(delete)

    datas structure:
    {
        'table_name': 'key_registry',
        'q_str': 'value,key_type',           # SELECT columns
        'where1': ['service', 'smtp-tide'],  # WHERE condition
        'in_data': {'service': '...', 'value': '...'},  # INSERT data
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
        raise ValueError(f"Unsupported query type or missing params: types={types}, keys={list(datas.keys())}")

    return sql


def init_db(db_path: str) -> None:
    """Initialize SQLite database and table schemas."""
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

    # Call log table
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
