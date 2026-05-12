# text-cli-modules/sqlite

可选 SQLite 模块 — 为 text-cli service 提供本地密钥存储。

## 设计

- **零耦合**: 不 import 任何 service 内部模块
- **纯函数**: db_path 外部注入，不持有连接状态
- **弹性**: 嵌在 service 中只需 import；拆成独立进程只需加 HTTP wrapper

## 表

- `key_registry` — 密钥存储 (service, value, key_type, registered_at)
- `call_log` — 操作审计

## 使用

```python
from text_cli_modules.sqlite import init_db, register, revoke, list_keys, get, get_all_keys

db = {'config': '/var/lib/text-cli-service/config.db'}
init_db(list(db.values())[0])

register(db, 'smtp-tide', 'password', 'smtp_password')
value = get(db, 'smtp-tide')
```
