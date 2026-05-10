# Key Management

**Directives:** `密钥;注册`, `密钥;撤销`, `密钥;列表`
**Dependencies:** `text_cli_modules/sqlite/`, `text_cli_modules/key/`
**Configuration:** None

Register, revoke, and list API keys in the service's local SQLite database. Keys are stored encrypted (XOR with `KEY_REGISTRY_SECRET`). Used by `ai_inference` and `ai_generate` handlers for API authentication.

## Install

```bash
cp examples/text-cli/key/handler.py server/python/handlers/key.py
```

## Usage

```
AI:key;register,zhipu,<your_api_key>,api_key
AI:key;register,modelscope,<your_api_key>,api_key
AI:key;list
AI:key;revoke,zhipu
```

---

# 密钥管理

**指令:** `密钥;注册`, `密钥;撤销`, `密钥;列表`
**依赖:** `text_cli_modules/sqlite/`, `text_cli_modules/key/`
**配置:** 无

在 service 本地 SQLite 数据库中注册、撤销和列出 API 密钥。密钥加密存储（与 `KEY_REGISTRY_SECRET` 异或）。供 `ai_inference` 和 `ai_generate` handler 调用 API 时使用。

## 安装

```bash
cp examples/text-cli/key/handler.py server/python/handlers/key.py
```

## 使用

```
指令:密钥;注册,zhipu,<your_api_key>,api_key
指令:密钥;注册,modelscope,<your_api_key>,api_key
指令:密钥;列表
指令:密钥;撤销,zhipu
```
