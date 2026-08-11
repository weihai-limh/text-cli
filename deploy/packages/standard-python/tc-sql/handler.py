"""
tc-sql handler — SQL query protocol layer.

Route + auth + execute. Any data owner joins by declaration in sql_permissions.json.
Four actions: query / tables / schema / count.
"""
import json
import logging
import sqlite3
import threading
from pathlib import Path

from core.registry import directive

logger = logging.getLogger(__name__)

_project_root: Path | None = None
_permissions: dict = {}


def init_tc_sql_handler(project_root: str):
    global _project_root, _permissions
    _project_root = Path(project_root)
    _permissions = _load_permissions()
    auth_count = sum(
        len(auth_perms) for auth_perms in _permissions.values()
        if isinstance(auth_perms, dict)
    )
    logger.info("tc-sql initialised: %d auth scopes, %d db aliases",
                len(_permissions), auth_count)


def _load_permissions() -> dict:
    perm_path = _project_root / "config" / "sql_permissions.json"
    if not perm_path.exists():
        logger.warning("sql_permissions.json not found at %s", perm_path)
        return {}
    with open(perm_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _get_auth_name() -> str | None:
    return getattr(threading.current_thread(), "_ai_im_auth_name", None)


def _parse_json_params(params: list[str], start_idx: int = 1) -> dict:
    """Parse JSON from params, handling comma-split reconstruction.

    The protocol parser splits params by comma, which can break JSON strings.
    Try direct parse first, then join remaining params with commas and retry.
    """
    if len(params) <= start_idx:
        raise ValueError("missing JSON parameter")

    direct = params[start_idx]
    try:
        return json.loads(direct)
    except json.JSONDecodeError:
        pass

    joined = ",".join(params[start_idx:])
    return json.loads(joined)


def _resolve_db(auth_name: str, db_alias: str) -> dict:
    if not _permissions:
        raise RuntimeError("sql_permissions not loaded")

    auth_perms = _permissions.get(auth_name)
    if not auth_perms:
        raise PermissionError(f"auth '{auth_name}' not found in sql_permissions")

    db_perm = auth_perms.get(db_alias)
    if not db_perm:
        raise PermissionError(f"database '{db_alias}' not found for auth '{auth_name}'")

    driver = db_perm.get("driver", "sqlite")
    if driver != "sqlite":
        raise ValueError(f"driver '{driver}' not yet supported")

    raw_path = db_perm.get("path")
    if not raw_path:
        raise ValueError(f"no path defined for database '{db_alias}'")

    return db_perm


def _resolve_db_path(db_perm: dict) -> str:
    return str(_project_root / db_perm["path"])


def _check_table_op(db_perm: dict, table: str, action: str):
    tables = db_perm.get("tables", {})
    table_perm = tables.get(table)
    if not table_perm:
        raise PermissionError(f"table '{table}' not in permissions for this database")
    ops = table_perm.get("ops", [])
    if action not in ops:
        raise PermissionError(f"table '{table}' does not allow '{action}'")


def _get_conn(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


@directive("tc-sql", "query", domain_alias="SQL查询", action_aliases={"query": "查询"})
def tc_sql_query(params: list[str]) -> dict:
    if len(params) < 2:
        return {"status": "error", "reason": "Usage: tc-sql;query,<db_alias>,<JSON>"}

    db_alias = params[0]
    try:
        query = _parse_json_params(params)
    except (json.JSONDecodeError, ValueError) as e:
        return {"status": "error", "reason": f"invalid JSON: {e}"}

    try:
        auth_name = _get_auth_name()
        if not auth_name:
            return {"status": "error", "reason": "not authenticated"}

        db_perm = _resolve_db(auth_name, db_alias)

        table = query.get("table")
        if not table:
            return {"status": "error", "reason": "missing 'table' in query JSON"}
        _check_table_op(db_perm, table, "query")

        columns = query.get("columns")
        if not columns or columns == "*":
            return {"status": "error", "reason": "specify columns, SELECT * not allowed"}

        limit = min(int(query.get("limit", 100)), 1000)

        db_path = _resolve_db_path(db_perm)
        conn = _get_conn(db_path)
        cursor = conn.cursor()

        where_clause = ""
        sql_params = []
        if "where" in query:
            where_data = query["where"]
            if isinstance(where_data, list) and len(where_data) == 2:
                col = where_data[0]
                val = where_data[1]
                where_clause = f" WHERE [{col}] = ?"
                sql_params.append(val)

        sql = f"SELECT {columns} FROM [{table}]{where_clause} LIMIT ?"
        sql_params.append(limit)

        cursor.execute(sql, sql_params)
        col_names = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = [dict(row) for row in cursor.fetchall()]
        count = len(rows)
        conn.close()

        return {
            "status": "ok",
            "table": table,
            "columns": col_names,
            "rows": rows,
            "count": count,
        }

    except PermissionError as e:
        return {"status": "error", "reason": str(e)}
    except Exception as e:
        logger.exception("tc-sql;query failed: db=%s table=%s", db_alias, query.get("table"))
        return {"status": "error", "reason": str(e)}


@directive("tc-sql", "tables", domain_alias="SQL查询", action_aliases={"tables": "表列表"})
def tc_sql_tables(params: list[str]) -> dict:
    if not params:
        return {"status": "error", "reason": "Usage: tc-sql;tables,<db_alias>"}

    db_alias = params[0]
    try:
        auth_name = _get_auth_name()
        if not auth_name:
            return {"status": "error", "reason": "not authenticated"}

        db_perm = _resolve_db(auth_name, db_alias)
        db_path = _resolve_db_path(db_perm)
        conn = _get_conn(db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row["name"] for row in cursor.fetchall()]
        conn.close()

        return {
            "status": "ok",
            "database": db_alias,
            "tables": tables,
            "count": len(tables),
        }

    except PermissionError as e:
        return {"status": "error", "reason": str(e)}
    except Exception as e:
        logger.exception("tc-sql;tables failed: db=%s", db_alias)
        return {"status": "error", "reason": str(e)}


@directive("tc-sql", "schema", domain_alias="SQL查询", action_aliases={"schema": "表结构"})
def tc_sql_schema(params: list[str]) -> dict:
    if len(params) < 2:
        return {"status": "error", "reason": "Usage: tc-sql;schema,<db_alias>,<JSON>"}

    db_alias = params[0]
    try:
        query = _parse_json_params(params)
    except (json.JSONDecodeError, ValueError) as e:
        return {"status": "error", "reason": f"invalid JSON: {e}"}

    try:
        auth_name = _get_auth_name()
        if not auth_name:
            return {"status": "error", "reason": "not authenticated"}

        db_perm = _resolve_db(auth_name, db_alias)

        table = query.get("table")
        if not table:
            return {"status": "error", "reason": "missing 'table' in schema JSON"}
        _check_table_op(db_perm, table, "schema")

        db_path = _resolve_db_path(db_perm)
        conn = _get_conn(db_path)
        cursor = conn.cursor()

        cursor.execute(f"PRAGMA table_info('{table}')")
        columns = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return {
            "status": "ok",
            "table": table,
            "columns": columns,
        }

    except PermissionError as e:
        return {"status": "error", "reason": str(e)}
    except Exception as e:
        logger.exception("tc-sql;schema failed: db=%s table=%s", db_alias, query.get("table"))
        return {"status": "error", "reason": str(e)}


@directive("tc-sql", "count", domain_alias="SQL查询", action_aliases={"count": "计数"})
def tc_sql_count(params: list[str]) -> dict:
    if len(params) < 2:
        return {"status": "error", "reason": "Usage: tc-sql;count,<db_alias>,<JSON>"}

    db_alias = params[0]
    try:
        query = _parse_json_params(params)
    except (json.JSONDecodeError, ValueError) as e:
        return {"status": "error", "reason": f"invalid JSON: {e}"}

    try:
        auth_name = _get_auth_name()
        if not auth_name:
            return {"status": "error", "reason": "not authenticated"}

        db_perm = _resolve_db(auth_name, db_alias)

        table = query.get("table")
        if not table:
            return {"status": "error", "reason": "missing 'table' in count JSON"}
        _check_table_op(db_perm, table, "count")

        db_path = _resolve_db_path(db_perm)
        conn = _get_conn(db_path)
        cursor = conn.cursor()

        where_clause = ""
        sql_params = []
        if "where" in query:
            where_data = query["where"]
            if isinstance(where_data, list) and len(where_data) == 2:
                col = where_data[0]
                val = where_data[1]
                where_clause = f" WHERE [{col}] = ?"
                sql_params.append(val)

        sql = f"SELECT COUNT(*) FROM [{table}]{where_clause}"
        cursor.execute(sql, sql_params)
        count = cursor.fetchone()[0]
        conn.close()

        return {
            "status": "ok",
            "table": table,
            "count": count,
        }

    except PermissionError as e:
        return {"status": "error", "reason": str(e)}
    except Exception as e:
        logger.exception("tc-sql;count failed: db=%s table=%s", db_alias, query.get("table"))
        return {"status": "error", "reason": str(e)}
