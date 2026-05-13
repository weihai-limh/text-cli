"""
Key registry — SQLite CRUD

Dependencies: database.py (get_sql_by_datas + post_sql_by_dbname)
Boundary: independent of service or copilot modules
Resilience: db_path injected externally, pure functions, stateless
"""

from text_cli_modules.sqlite.database import get_sql_by_datas, post_sql_by_dbname


def register(db_path: dict, service: str, value: str, key_type: str) -> dict:
    """
    Register a key.
    Returns: {'ok': True, 'service': service} or {'ok': False, 'error': 'key_exists'}
    """
    # Check if already exists
    existing = get(db_path, service)
    if existing:
        return {'ok': False, 'error': 'key_exists',
                'detail': f'Key {service} already exists, revoke first'}

    sql = get_sql_by_datas('in', {
        'table_name': 'key_registry',
        'in_data': {
            'service': service,
            'value': value,
            'key_type': key_type,
        }
    })
    post_sql_by_dbname(db_path, sql)

    _log(db_path, 'KEY_REGISTER', service, f'type={key_type}')

    return {'ok': True, 'service': service, 'key_type': key_type}


def revoke(db_path: dict, service: str) -> dict:
    """
    Revoke a key.
    Returns: {'ok': True, 'service': service} or {'ok': False, 'error': 'key_not_found'}
    """
    existing = get(db_path, service)
    if not existing:
        return {'ok': False, 'error': 'key_not_found',
                'detail': f'Key {service} not found'}

    sql = get_sql_by_datas('del', {
        'table_name': 'key_registry',
        'where1': ['service', service]
    })
    post_sql_by_dbname(db_path, sql)

    _log(db_path, 'KEY_REVOKE', service)

    return {'ok': True, 'service': service}


def list_keys(db_path: dict) -> list:
    """
    List registered keys (values not returned).
    Returns: [{'service': 'smtp-tide', 'key_type': 'smtp_password', 'registered_at': '...'}, ...]
    """
    sql = get_sql_by_datas('q', {
        'table_name': 'key_registry',
        'q_str': 'service,key_type,registered_at',
    })

    result = post_sql_by_dbname(db_path, sql)
    if not result:
        return []

    # result is dict: {service: [key_type, registered_at]}
    if isinstance(result, dict):
        return [
            {
                'service': svc,
                'key_type': vals[0] if len(vals) > 0 else 'unknown',
                'registered_at': vals[1] if len(vals) > 1 else 'unknown',
            }
            for svc, vals in result.items()
        ]
    return []


def get(db_path: dict, service: str) -> str | None:
    """
    Retrieve a key's plaintext value.
    Returns: value string or None
    """
    sql = get_sql_by_datas('q', {
        'table_name': 'key_registry',
        'q_str': 'value',
        'where1': ['service', service]
    })

    result = post_sql_by_dbname(db_path, sql)
    if not result:
        return None

    # result may be single value, list, or dict
    if isinstance(result, list) and len(result) > 0:
        return result[0]
    elif isinstance(result, dict):
        return list(result.keys())[0] if result else None
    elif isinstance(result, str):
        return result
    return None


def get_all_keys(db_path: dict) -> dict[str, str]:
    """
    Retrieve all keys (for proxy injection).
    Returns: {'smtp-tide': 'password123', 'bigmodel-embedding-3': 'key456'}
    """
    sql = get_sql_by_datas('q', {
        'table_name': 'key_registry',
        'q_str': 'service,value',
    })

    result = post_sql_by_dbname(db_path, sql)
    if not result:
        return {}

    if isinstance(result, dict):
        # {service: [value]} → {service: value}
        return {svc: vals[0] if vals else '' for svc, vals in result.items()}
    return {}


def _log(db_path: dict, action: str, service: str, detail: str = ''):
    """Write audit log entry."""
    try:
        sql = get_sql_by_datas('in', {
            'table_name': 'call_log',
            'in_data': {
                'action': action,
                'service': service,
                'detail': detail,
            }
        })
        post_sql_by_dbname(db_path, sql)
    except Exception:
        pass  # Log write failure does not block main flow
