# web-utils — Web 工具

Web 实用工具包：获取公网 IP、XOR 加密解密。部署在腾讯云 CloudBase 云函数上。

## 调用方式

### 直接 HTTP 调用（已知端点时）

```bash
curl -s -X POST <端点URL>/text-cli/cli \
  --header 'Content-Type: application/json' \
  --data-raw '{"prompt":"AI:web-utils;get_public_ip"}'
```

### 通过 A3 路由（配置聚合路由后）

```bash
tc "AI:web-utils;get_public_ip"
tc "AI:web-utils;xor_encrypt,hello world,mykey"
tc "AI:web-utils;xor_decrypt,68656c6c6f20776f726c64,mykey"
```

## 指令

### 获取公网 IP

```bash
AI:web-utils;get_public_ip
```

返回：`{"status": "ok", "result": "203.0.113.1"}`

### XOR 加密

```bash
AI:web-utils;xor_encrypt,hello world,mykey
```

返回：`{"status": "ok", "result": "68656c6c6f20776f726c64"}`

### XOR 解密

```bash
AI:web-utils;xor_decrypt,68656c6c6f20776f726c64,mykey
```

返回：`{"status": "ok", "result": "hello world"}`

## 注意事项

- 本包部署在腾讯云 CloudBase 云函数，不通过 `text-cli;install` 安装
- 响应遵循协议现代信封 `{rst_types, rst_data, rst_err}`（SPEC §1.2.2）：
  - `rst_data` **直接承载业务结果**（即下方各指令示例中的 `{"status":"ok","result":"..."}`），不再使用旧的 `rst_data.text` 嵌套 + 多余 `JSON.stringify`。
  - `rst_err` 为空字符串表示成功；非空为错误码（如 `ACTION_NOT_FOUND` / `MISSING_PARAM` / `INVALID_HEX`），调用方据此判定 `ok`。
- 经 cloudbase router 转发时，router 透传本包信封，不二次包裹。
- 参数解析采用协议级括号深度追踪逗号拆分（与 Python service 一致）：含逗号/括号的参数（如 JSON）不会被错误切分。

## 源码

- 仓库位置：`text-cli-package/dev/web-utils/`
- 归档位置：`text-cli-package/src/open/web-utils/`
- 运行时：Node.js（`wx-server-sdk`）
