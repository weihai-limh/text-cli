# key · 密钥管理

注册、撤销和列出 API 密钥，支持加密本地存储。

## 安装

```
AI:text-cli;install,key
```

## 依赖

**运行时模块**（需部署到服务）：
- `text_cli_modules/key/` — 密钥注册表（注册、撤销、列表、配额追踪）
- `text_cli_modules/sqlite/` — SQLite 数据库层

## 安全模型

- **传输层**：明文与 `XOR_KEY_<服务名>` 做 XOR 加密后以 hex 传输
- **存储层**：注册后以 `KEY_REGISTRY_SECRET` 加密存盘
- **列表安全**：`key;list` 仅返回服务名和类型，不暴露密钥值

## 指令

| 指令 | 说明 |
|------|------|
| `key;register,<服务名>,<值>[,<值2>],<密钥类型>` | 注册密钥。单凭据：`key;register,svc,值,api_key`。双凭据：`key;register,svc,id,secret,cloud` |
| `key;revoke,<服务名>` | 撤销密钥 |
| `key;list` | 列出所有密钥（不暴露值） |
| `key;quota-track,<服务名>[,<目标>,...]` | 设置或清除配额追踪 |
| `key;export-xor,<服务名>` | 导出 XOR 加密密钥，用于向外部系统安全注入 |

## 示例

```
AI:密钥;注册,my-api,sk-abc123,api_key
→ Key registered: my-api (type=api_key, cred_count=1)

AI:密钥;列表
→ Registered keys: 2
    my-api (api_key, cred_count=1)
    my-cloud (cloud_credentials, cred_count=2)

AI:密钥;撤销,my-api
→ Key revoked: my-api
```

## XOR 加密原理

调用方在本地执行 XOR 加密后传输密文，copilot/service 端存储前二次加密：

```python
import os

def xor_encrypt_hex(plain: str, xor_key: str) -> str:
    plain_bytes = plain.encode('utf-8')
    key_bytes = xor_key.encode('utf-8')
    result = bytes([plain_bytes[i] ^ key_bytes[i % len(key_bytes)]
                    for i in range(len(plain_bytes))])
    return result.hex()
```

## 架构

```
A6 SQL 模块
  ├── handler.py           — @directive 注册 + 业务逻辑
  ├── schema.json          — 指令声明
  ├── text_cli_modules/key/ — 密钥注册表（运行时依赖）
  └── text_cli_modules/sqlite/ — 数据库层（运行时依赖）
```

SQLite 表：`keys(service, key_type, value_encrypted, value2_encrypted?, cred_count, quota_track, registered_at)`
