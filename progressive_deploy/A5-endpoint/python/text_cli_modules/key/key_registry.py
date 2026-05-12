"""
密钥注册表 — SQLite CRUD

依赖: database.py（get_sql_by_datas + post_sql_by_dbname）
边界: 不依赖 service 或 copilot 的任何模块
弹性: db_path 外部注入，纯函数，零状态
"""

from text_cli_modules.sqlite.database import get_sql_by_datas, post_sql_by_dbname


def register(db_path: dict, service: str, value: str, key_type: str) -> dict:
    """
    注册密钥。
    返回: {'ok': True, 'service': service} 或 {'ok': False, 'error': 'key_exists'}
    """
    # 先查是否存在
    existing = get(db_path, service)
    if existing:
        return {'ok': False, 'error': 'key_exists',
                'detail': f'密钥 {service} 已存在，请先撤销'}

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
    撤销密钥。
    返回: {'ok': True, 'service': service} 或 {'ok': False, 'error': 'key_not_found'}
    """
    existing = get(db_path, service)
    if not existing:
        return {'ok': False, 'error': 'key_not_found',
                'detail': f'密钥 {service} 不存在'}

    sql = get_sql_by_datas('del', {
        'table_name': 'key_registry',
        'where1': ['service', service]
    })
    post_sql_by_dbname(db_path, sql)

    _log(db_path, 'KEY_REVOKE', service)

    return {'ok': True, 'service': service}


def list_keys(db_path: dict) -> list:
    """
    列出已注册密钥（不返回密钥值）。
    返回: [{'service': 'smtp-tide', 'key_type': 'smtp_password', 'registered_at': '...'}, ...]
    """
    sql = get_sql_by_datas('q', {
        'table_name': 'key_registry',
        'q_str': 'service,key_type,registered_at',
    })

    result = post_sql_by_dbname(db_path, sql)
    if not result:
        return []

    # result 是 dict: {service: [key_type, registered_at]}
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
    获取密钥明文值。
    返回: 值字符串 或 None
    """
    sql = get_sql_by_datas('q', {
        'table_name': 'key_registry',
        'q_str': 'value',
        'where1': ['service', service]
    })

    result = post_sql_by_dbname(db_path, sql)
    if not result:
        return None

    # result 可能是单值、list 或 dict
    if isinstance(result, list) and len(result) > 0:
        return result[0]
    elif isinstance(result, dict):
        # {value: []} → value 本身
        return list(result.keys())[0] if result else None
    elif isinstance(result, str):
        return result
    return None


def get_all_keys(db_path: dict) -> dict[str, str]:
    """
    获取所有密钥（用于 proxy 注入）。
    返回: {'smtp-tide': 'password123', 'bigmodel-embedding-3': 'key456'}
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
    """写入审计日志"""
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
        pass  # 日志写入失败不影响主流程
