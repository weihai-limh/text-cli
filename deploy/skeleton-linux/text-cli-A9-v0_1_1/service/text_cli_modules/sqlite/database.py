"""
SQLite thin wrapper — structured SQL generation + adaptive result parsing.
Pure functions, zero external dependencies, db_path injected externally.
"""

import sqlite3

# ── Whitelists for SQL generation ──
VALID_TABLES = frozenset({"key_registry", "call_log", "token_registry", "token_call_logs", "peer_credentials"})
VALID_FIELDS = frozenset({
    "service", "value", "value2", "key_type", "registered_at",
    "cred_count", "quota_track", "token", "enabled", "quota_limit",
    "used_count", "expires_at", "created_at", "action", "detail",
    "domain", "status", "error_msg", "duration_ms", "ts",
    "token_id", "max_requests_per_minute", "is_active",
})


def post_sql_by_dbname(db_path: dict, sql: str, params: tuple = ()):
    db_file = next(iter(db_path.values())) if isinstance(db_path, dict) else db_path
    rst_list = []
    rst_dict = {}
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    if 'SELECT' in sql.upper():
        cursor.execute(sql, params)
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
        rst = cursor.execute(sql, params)
        conn.commit()
    conn.close()
    return rst


def get_sql_by_datas(types: str, datas: dict) -> tuple[str, tuple]:
    """Build parameterized SQL from structured datas dict.

    Returns (sql_string, params_tuple) for use with sqlite3 parameter binding.
    Table names and field names are validated against whitelists.
    """
    params = []

    # Validate table_name
    table_name = datas.get("table_name", "")
    if table_name not in VALID_TABLES:
        raise ValueError(f"Invalid table name: '{table_name}'")

    # Build WHERE clause with parameterized value
    where_part = ""
    if 'where1' in datas:
        field = datas['where1'][0]
        if field not in VALID_FIELDS:
            raise ValueError(f"Invalid field name: '{field}'")
        where_part = f" WHERE {field} = ?"
        params.append(datas['where1'][1])

    # SELECT column list
    q_obj_part = datas.get('q_str', '*')

    # INSERT data
    if 'in_data' in datas:
        # Validate all field names
        for k in datas["in_data"]:
            if k not in VALID_FIELDS:
                raise ValueError(f"Invalid field name: '{k}'")
        data_k = ','.join(datas["in_data"].keys())
        data_placeholders = ','.join(['?'] * len(datas["in_data"]))
        data_values = list(datas["in_data"].values())
        params.extend(data_values)

    # UPDATE SET clause
    if 'up_list1' in datas:
        field = datas['up_list1'][0]
        if field not in VALID_FIELDS:
            raise ValueError(f"Invalid field name: '{field}'")
        set_part = f" SET {field} = ?"
        params.append(datas['up_list1'][1])

    if types == 'q':
        sql = f"SELECT {q_obj_part} FROM {table_name}{where_part}"
    elif types == 'up' and 'up_list1' in datas:
        sql = f"UPDATE {table_name}{set_part}{where_part}"
    elif types == 'in' and 'in_data' in datas:
        sql = f"INSERT INTO {table_name} ({data_k}) VALUES ({data_placeholders})"
    elif types == 'del' and 'where1' in datas:
        sql = f"DELETE FROM {table_name}{where_part}"
    else:
        raise ValueError(f"Unsupported query type: types={types}")
    return sql, tuple(params)


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
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS token_registry (
            token TEXT PRIMARY KEY,
            enabled INTEGER DEFAULT 1,
            quota_limit INTEGER,
            used_count INTEGER DEFAULT 0,
            expires_at TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS token_call_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT,
            domain TEXT,
            action TEXT,
            status TEXT,
            error_msg TEXT,
            duration_ms INTEGER,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS peer_credentials (
            peer TEXT PRIMARY KEY,
            service_token TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()
