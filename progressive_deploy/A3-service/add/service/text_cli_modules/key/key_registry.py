"""
密钥注册表 v2 — SQLite CRUD + 双凭据 + 配额追踪

v2 新增:
  - 双凭据支持 (cred_count=2: value + value2)
  - quota_track 字段 (JSON 数组, 由 key;quota-track 指令管理)
  - dispatch 回调注入 (key.get 时触发配额检查)
  - 优雅降级 (dispatch 未注入/异常 → 跳过检查)

依赖: database.py (get_sql_by_datas + post_sql_by_dbname)
边界: 不依赖 service 或 copilot 的任何模块
弹性: db_path 外部注入, 纯函数, 零状态
"""

import json
import logging
import sqlite3

from text_cli_modules.sqlite.database import get_sql_by_datas, post_sql_by_dbname

logger = logging.getLogger(__name__)

_dispatch_fn = None


def set_dispatch(fn):
    global _dispatch_fn
    _dispatch_fn = fn
    logger.info("key_registry: dispatch callback injected")


def _has_dispatch() -> bool:
    return _dispatch_fn is not None


def _dispatch_quota_check(target: str) -> dict | None:
    if not _has_dispatch():
        return None
    try:
        result = _dispatch_fn("quota", "check", [target])
        return result
    except Exception as e:
        logger.warning("quota;check dispatch failed for %s: %s", target, e)
        return None


def register(db_path: dict, service: str, *values: str, key_type: str) -> dict:
    existing = get(db_path, service)
    if existing:
        return {'ok': False, 'error': 'key_exists',
                'detail': f'密钥 {service} 已存在，请先撤销'}
    if not values:
        return {'ok': False, 'error': 'missing_value',
                'detail': '至少需要一个凭据值'}
    cred_count = min(len(values), 2)
    v1 = values[0]
    v2 = values[1] if len(values) >= 2 else None
    sql = get_sql_by_datas('in', {
        'table_name': 'key_registry',
        'in_data': {
            'service': service,
            'value': v1,
            'value2': v2 or '',
            'cred_count': str(cred_count),
            'key_type': key_type,
        }
    })
    post_sql_by_dbname(db_path, sql)
    _log(db_path, 'KEY_REGISTER', service,
         f'type={key_type} cred_count={cred_count}')
    return {'ok': True, 'service': service, 'key_type': key_type,
            'cred_count': cred_count}


def revoke(db_path: dict, service: str) -> dict:
    existing = get_raw(db_path, service)
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
    sql = get_sql_by_datas('q', {
        'table_name': 'key_registry',
        'q_str': 'service,key_type,cred_count,quota_track,registered_at',
    })
    result = post_sql_by_dbname(db_path, sql)
    if not result:
        return []
    if isinstance(result, dict):
        return [
            {
                'service': svc,
                'key_type': vals[0] if len(vals) > 0 else 'unknown',
                'cred_count': int(vals[1]) if len(vals) > 1 and vals[1] else 1,
                'quota_track': _parse_quota_track(vals[2]) if len(vals) > 2 else None,
                'registered_at': vals[3] if len(vals) > 3 else 'unknown',
            }
            for svc, vals in result.items()
        ]
    return []


def get_raw(db_path: dict, service: str) -> dict | None:
    sql = get_sql_by_datas('q', {
        'table_name': 'key_registry',
        'q_str': 'value,value2,cred_count,quota_track',
        'where1': ['service', service]
    })
    result = post_sql_by_dbname(db_path, sql)
    if not result:
        return None
    if isinstance(result, dict):
        for svc, vals in result.items():
            return {
                'value': svc,
                'value2': vals[0] if len(vals) > 0 and vals[0] else None,
                'cred_count': int(vals[1]) if len(vals) > 1 and vals[1] and vals[1] != 'None' else 1,
                'quota_track': _parse_quota_track(vals[2]) if len(vals) > 2 else None,
            }
    return None


def get(db_path: dict, service: str) -> str | list[str] | None:
    row = get_raw(db_path, service)
    if not row:
        return None
    quota_targets = row.get('quota_track')
    if quota_targets and _has_dispatch():
        for target in quota_targets:
            try:
                r = _dispatch_quota_check(target)
                if r and r.get('status') == 'stop':
                    logger.info("key_registry: quota exhausted for %s (target=%s)", service, target)
                    _log(db_path, 'QUOTA_BLOCKED', service, f'target={target} status=stop')
                    return None
                elif r and r.get('status') == 'ok':
                    logger.debug("key_registry: quota ok for %s (target=%s remaining=%s)", service, target, r.get('remaining'))
            except Exception:
                logger.warning("key_registry: quota check exception for %s/%s", service, target, exc_info=True)
    if row.get('cred_count', 1) >= 2 and row.get('value2'):
        return [row['value'], row['value2']]
    return row['value']


def get_all_keys(db_path: dict) -> dict[str, str]:
    sql = get_sql_by_datas('q', {
        'table_name': 'key_registry',
        'q_str': 'service,value',
    })
    result = post_sql_by_dbname(db_path, sql)
    if not result:
        return {}
    if isinstance(result, dict):
        return {svc: vals[0] if vals else '' for svc, vals in result.items()}
    return {}


def set_quota_track(db_path: dict, service: str, targets: list[str] | None) -> dict:
    existing = get_raw(db_path, service)
    if not existing:
        return {'ok': False, 'error': 'key_not_found',
                'detail': f'密钥 {service} 不存在'}
    if not targets:
        quota_track_str = None
    else:
        quota_track_str = json.dumps(targets, ensure_ascii=False)
    db_file = list(db_path.values())[0] if isinstance(db_path, dict) else db_path
    conn = sqlite3.connect(db_file)
    conn.execute(
        "UPDATE key_registry SET quota_track = ? WHERE service = ?",
        (quota_track_str, service)
    )
    conn.commit()
    conn.close()
    _log(db_path, 'KEY_QUOTA_TRACK', service, f'targets={targets if targets else "cleared"}')
    return {'ok': True, 'service': service, 'quota_track': targets}


def get_quota_track(db_path: dict, service: str) -> list[str] | None:
    row = get_raw(db_path, service)
    if not row:
        return None
    return row.get('quota_track')


def _parse_quota_track(raw: str | None) -> list[str] | None:
    if not raw or not raw.strip():
        return None
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else None
    except (json.JSONDecodeError, TypeError):
        return None


def _log(db_path: dict, action: str, service: str, detail: str = ''):
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
        pass
