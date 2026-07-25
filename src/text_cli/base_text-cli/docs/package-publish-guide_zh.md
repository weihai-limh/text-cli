# 指令包发布指南

> 面向包作者。一份符合 SPEC 的指令包应该长什么样。
> 协议字段语义以 [SPEC](../../../docs/SPEC_zh.md) 为权威；制作方法见 [package-dev-guide_zh.md](package-dev-guide_zh.md)。

---

## 0. 分发与授权

- 指令包的**分发协议由包作者自行决定**（MIT / Apache-2.0 / GPL / 闭源 / …），SPEC 不做限制。
- 官方仓库提供多种**兼容 SPEC 的运行时**，主要维护这两部分：协议演进 + 运行时迭代。不参与包的策展或分发审核。

---

## 1. 文件结构

```
<package-id>/
├── schema.json              ← 必须
├── handler.py               ← python 包必须
│   或 <entry>.js            ← node 包必须（禁止 handler.js）
├── README.md                ← 建议
├── requirements.txt         ← 按需
├── text_cli_modules/        ← 按需
├── whitelist.json           ← cmd runtime（替代 handler）
├── path/                    ← path runtime（替代 handler）
└── config/                  ← 按需
```

> node 包必须用 `<package-id>.js`——安装器按文件名定位，多个包同名文件会互相覆盖。

---

## 2. schema.json 规范

> 以下字段以 SPEC §4.2 为权威。本指南给出 Checklist + 反例。

### 2.1 顶层字段

| 字段 | 必填 | 合法值 |
|------|------|--------|
| `id` | ✅ | 连字符格式，如 `my-package` |
| `type` | ✅ | `native` / `nocode` / `aggregate` / `path` |
| `name` | ✅ | 英文名 |
| `name_zh` | ✅ | 中文名（外文前缀小写） |
| `runtime` | ✅ | `python` / `node` / `mcp` / `cmd` / `path` / `aggregate` |
| `version` | ✅ | Semver |
| `category` | ✅ | 如 `数据处理` / `AI` / `地理服务` |
| `locales` | ✅ | `["zh", "en"]` |
| `trust` | ✅ | `internal` / `community` / `public` |
| `description` | ✅ | 英文一句话 |
| `description_zh` | 否 | 中文一句话 |
| `entry` | 否 | 如 `"handler.py"` |
| `mcp_server` | 否 | MCP server 名 |
| `entry_runtimes` | 否 | `["python", "node"]` |
| `requires` | 否 | 见 §2.2 |
| `credentials` | 否 | 见 §2.3 |
| `tables` | 否 | 自建表 CREATE TABLE 声明 |
| `directives` | ✅ | 见 §2.4，至少一条 |

### 2.2 requires

```json
"requires": {
  "pip": ["requests>=2.28"],
  "modules": ["text_cli_modules/my_module/"],
  "tc_packages": ["other-package"],
  "npm": ["@scope/name@^1.0"],
  "binaries": {
    "some-tool": {"source": "system", "min_version": "1.0"}
  },
  "service_db": ["token_registry"]
}
```

| 子字段 | 说明 |
|--------|------|
| `pip` | Python 包，安装时自动 `pip install` |
| `modules` | 运行时模块路径 |
| `tc_packages` | 指令包间依赖 |
| `npm` | Node 包，安装时自动 `npm install` |
| `binaries` | 系统二进制依赖 |
| `service_db` | 依赖的服务端数据库表 |

零依赖写 `"requires": {}`。

### 2.3 credentials

```json
"credentials": [
  {
    "name": "my_api_key",
    "description_en": "API key",
    "description_zh": "API 密钥",
    "storage": "key_registry",
    "register_cmd": "key;register,my_api_key,<key>,api_key"
  }
]
```

无凭据需求时省略整段。

### 2.4 directives

每条指令至少填写以下字段：

| 字段 | 必填 | 示例 |
|------|------|------|
| `domain` | ✅ | `"my-pkg"` |
| `domain_zh` | ✅ | `"我的包"` |
| `action` | ✅ | `"do-something"` |
| `action_zh` | ✅ | `"做某事"` |
| `usage` | ✅ | `"my-pkg;do-something,<param>"` |
| `usage_zh` | ✅ | `"我的包;做某事,<参数>"` |
| `description` | ✅ | 英文一句话 |
| `description_zh` | ✅ | 中文一句话 |
| `params` | 建议 | `["param"]` |
| `params_desc` | 建议 | `{"param": "说明"}` |
| `outputs` | 建议 | `["field1"]` |
| `estimated_time` | 否 | `"30s"` |
| `estimated_time_note` | 否 | 预估时间说明 |

### 2.5 反例

| ❌ 错误 | ✅ 正确 |
|---------|---------|
| `"type": "api"` | `"type": "native"` |
| 返回 `{"data": {"text": "..."}}` | 返回 `{"text": "..."}`（无 data 嵌套） |
| `"name_zh": "Tide天气"` | `"name_zh": "tide天气"` |
| `"via ZhiPu API"` | `"via configurable AI provider"` |
| handler.py 硬编码密钥 | 密钥走 credentials + key registry |
| docstring 写部署路径 | docstring 只写包提供什么指令 |

### 2.6 多语言向量一致性

`name_zh`、`domain_zh` 中的外文前缀**小写**——保持中文向量嵌入空间一致。`domain` 与 `domain_zh` 语义对齐。

---

## 3. README

```markdown
# <name>

一句话描述。

## Install
text-cli;install,<id>

## Directives
| 指令 | 说明 |

## Example
最少一个完整调用示例。

## Dependencies
- 运行时模块 / 凭据 / pip 依赖
```

---

## 4. 返回信封

handler 返回格式：

```json
{"status": "ok", "result": "...", "detail": "..."}
{"status": "error", "message": "..."}
```

业务字段放在 `status` 同级，不嵌套 `data` 层。`message` 可读、不泄露密钥或堆栈。
