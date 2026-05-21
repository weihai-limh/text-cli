"""
SQLite thin wrapper — structured SQL generation + adaptive result parsing.
Pure functions, zero external dependencies, db_path injected externally.
"""

import sqlite3


def post_sql_by_dbname(db_path: dict, sql: str):
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
        raise ValueError(f"Unsupported query type: types={types}")
    return sql


def _migrate_key_registry(cursor):
    existing = {row[1] for row in cursor.execute("PRAGMA table_info(key_registry)").fetchall()}
    for col, col_def in [
        ("value2",      "TEXT"),
        ("cred_count",  "INTEGER DEFAULT 1"),
        ("quota_track", "TEXT"),
    ]:
        if col not in existing:
            cursor.execute(f"ALTER TABLE key_registry ADD COLUMN {col} {col_def}")


def init_db(db_path: str) -> None:
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
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS call_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL DEFAULT (datetime('now')),
            action TEXT NOT NULL,
            service TEXT,
            detail TEXT
        )
    """)
    _migrate_key_registry(cursor)
    conn.commit()
    conn.close()
