# 密钥管理指令示例

> Domain: `密钥` | 更新: 2026-05-09 | 实现: `server/agent-copilot/handlers/key.py`

## 指令清单

| 指令 | 级别 | 参数 | 说明 |
|------|------|------|------|
| `密钥;注册` | write | 服务名, 密文(hex), 密钥类型 | 注册服务密钥 |
| `密钥;撤销` | write | 服务名 | 撤销已注册密钥 |
| `密钥;列表` | read | (无) | 列出已注册密钥（不返回密钥值） |

---

## 指令:密钥;注册

**用途**：将服务密钥安全注册到本地密钥库。

**参数**：
| # | 参数 | 必填 | 说明 |
|---|------|------|------|
| 1 | 服务名 | ✅ | 唯一标识，如 `smtp-tide`、`bigmodel-embedding-3` |
| 2 | 密文(hex) | ✅ | XOR 加密后的 hex 字符串 |
| 3 | 密钥类型 | ✅ | 如 `smtp_password`、`api_key`、`github_token` |

**安全模型**：
- **传输层**：明文与 `XOR_KEY` 做 XOR 后转 hex 传输
- **存储层**：注册后以 `KEY_REGISTRY_SECRET` 二次加密存盘
- **审计**：注册操作写入审计日志

**XOR 加密帮助**（调用方在本地执行）：
```python
# 将明文密码加密为可传输的密文
import os

def xor_encrypt_hex(plain: str, xor_key: str) -> str:
    plain_bytes = plain.encode('utf-8')
    key_bytes = xor_key.encode('utf-8')
    result = bytes([plain_bytes[i] ^ key_bytes[i % len(key_bytes)] for i in range(len(plain_bytes))])
    return result.hex()

cipher = xor_encrypt_hex('my_smtp_password', os.environ['XOR_KEY_smtp_tide'])
print(cipher)  # 发送给 copilot
```

**调用示例**：

纯文本（协议原生）：
```
指令:密钥;注册,smtp-tide,a1b2c3d4e5f6...,smtp_password
```

HTTP（通过 service 代理）：
```bash
curl -X POST http://localhost:8000/cli/text_cli \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "command": "密钥;注册",
    "parameters": ["smtp-tide", "a1b2c3d4e5f6...", "smtp_password"]
  }'
```

**响应**：
```json
{
  "rst_types": "text",
  "rst_data": {
    "text": "密钥已注册: smtp-tide",
    "service": "smtp-tide",
    "key_type": "smtp_password"
  }
}
```

---

## 指令:密钥;撤销

**用途**：从密钥库中移除指定服务密钥。

**调用示例**：

纯文本（协议原生）：
```
指令:密钥;撤销,smtp-tide
```

HTTP（通过 service 代理）：
```bash
curl -X POST http://localhost:8000/cli/text_cli \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "command": "密钥;撤销",
    "parameters": ["smtp-tide"]
  }'
```

**响应**：
```json
{
  "rst_types": "text",
  "rst_data": {
    "text": "密钥已撤销: smtp-tide"
  }
}
```

---

## 指令:密钥;列表

**用途**：查看已注册的密钥清单（不返回密钥值）。

**调用示例**：

纯文本（协议原生）：
```
指令:密钥;列表
```

HTTP（通过 service 代理）：
```bash
curl -X POST http://localhost:8000/cli/text_cli \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "command": "密钥;列表",
    "parameters": []
  }'
```

**响应**：
```json
{
  "rst_types": "text",
  "rst_data": {
    "text": "已注册密钥: 3 个\n- smtp-tide (smtp_password)\n- bigmodel-embedding-3 (api_key)\n- zhipu-glm-4-flash (api_key)",
    "count": 3,
    "services": ["smtp-tide", "bigmodel-embedding-3", "zhipu-glm-4-flash"]
  }
}
```

---

## 完整链路：注册 → 使用 → 撤销

纯文本（协议原生）：
```
# 1. 注册
指令:密钥;注册,smtp-tide,<XOR_CIPHER_HEX>,smtp_password

# 2. 发送邮件（mail.py 自动从 key_registry 读取 SMTP 密码）
指令:邮件;发送,tide@10000.world,测试,正文

# 3. 撤销
指令:密钥;撤销,smtp-tide
```

HTTP（通过 service 代理）：
```bash
# 1. 注册
curl -X POST http://localhost:8000/cli/text_cli \
  -H "Authorization: Bearer <TOKEN>" \
  -d '{"command": "密钥;注册", "parameters": ["smtp-tide", "<XOR_CIPHER_HEX>", "smtp_password"]}'

# 2. 发送邮件
curl -X POST http://localhost:8000/cli/text_cli \
  -H "Authorization: Bearer <TOKEN>" \
  -d '{"command": "邮件;发送", "parameters": ["tide@10000.world", "测试", "正文"]}'

# 3. 撤销
curl -X POST http://localhost:8000/cli/text_cli \
  -H "Authorization: Bearer <TOKEN>" \
  -d '{"command": "密钥;撤销", "parameters": ["smtp-tide"]}'
```

## 实现说明

- **handler**：`server/agent-copilot/handlers/key.py`（KeyRegistry 类 + KeyHandlers 类）
- **存储**：`key_registry.json`（本地文件，AES 二次加密）
- **依赖**：`KEY_REGISTRY_SECRET` 环境变量（运行时注入，不入仓库）
- **模式**：copilot 本地处理；service 通过 SQLite 模块处理（互替模式 A）


