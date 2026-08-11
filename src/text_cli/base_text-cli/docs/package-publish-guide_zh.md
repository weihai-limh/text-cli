# 指令包发布指南

> 面向包作者。一份符合 SPEC 的指令包应该长什么样——跨语言、跨运行时的统一结构。
> 旁路运行时兼容性：符合本指南的 `native-python` 包可直接被 `textcli-loader`（PyPI）加载，`native-js` 包可直接被 `textcli-core`（npm）加载——一次编写，多运行时可用。

---

## 0. 分发与授权

- 指令包的**分发协议由包作者自行决定**（MIT / Apache-2.0 / GPL / 闭源 / …），SPEC 不做限制。
- 官方仓库提供多种**兼容 SPEC 的运行时**，主要维护这两部分：协议演进 + 运行时迭代。不参与包的策展或分发审核。

---

## 1. 文件结构

### 1.1 Python 包

```
<package-id>/
├── schema.json              ← 必须
├── handler.py               ← 必须（@directive 装饰器注册）
├── README.md                ← 建议
├── requirements.txt         ← 按需
├── text_cli_modules/        ← 按需
└── config/                  ← 按需
```

### 1.2 JavaScript 包

```
<package-id>/
├── schema.json              ← 必须
├── handler.js               ← 必须（声明式 module.exports 注册）
├── README.md                ← 建议
├── package.json             ← 按需
└── config/                  ← 按需
```

JS handler 使用**声明式导出结构**：

```javascript
module.exports = {
  domainAlias: "中文别名",
  directives: {
    "action-name": {
      handler: (params, context) => { /* params: string[] → object */ },
      actionAliases: ["中文动作别名"]
    }
  }
};
```

### 1.3 MCP 桥接包

```
<package-id>/
├── schema.json              ← 必须（type: "native", runtime: "mcp"）
├── service-descriptor.json  ← 必须（mcporter 映射表）
└── README.md                ← 建议
```

MCP 桥接包零 handler 代码——每条指令在 `schema.json` 中通过 `mcp_tool` 字段指向 MCP server 的 tool 名，`service-descriptor.json` 定义 MCP 连接参数。

### 1.4 其他形态

| 形态 | 替代 handler 的文件 | 说明 |
|------|-------------------|------|
| cmd | `whitelist.json` | 命令行工具白名单 |
| path | `path/` 目录 | 路径编排（纯声明，无 handler） |
| nocode | `knowledge/` 目录 | 零代码知识库（见 nocode 指南） |

---

## 2. schema.json 规范

> 以下字段以 SPEC §4.2 为权威。本指南给出 Checklist + 反例。

### 2.1 顶层字段

| 字段 | 必填 | 合法值 |
|------|------|--------|
| `id` | ✅ | 连字符格式，如 `my-package` |
| `type` | ✅ | `native` / `nocode` / `aggregate` / `pipeline` |
| `name` | ✅ | 英文名 |
| `name_zh` | 否 | 中文名（外文前缀小写） |
| `runtime` | ✅ | `python` / `js` / `mcp` / `cmd` / `path` / `aggregate` |
| `version` | ✅ | Semver |
| `category` | ✅ | 如 `utility` / `weather` / `ai` / `dev-tools` |
| `locales` | ✅ | `["zh", "en"]` |
| `trust` | ✅ | `internal` / `community` / `public` |
| `description` | ✅ | 英文一句话 |
| `description_zh` | 否 | 中文一句话 |
| `entry` | 否 | 如 `"handler.py"` |
| `mcp_server` | 否 | MCP server 名 |
| `entry_runtimes` | 否 | `["python", "js"]` |
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
| `domain_zh` | 否 | `"我的包"` |
| `action` | ✅ | `"do-something"` |
| `action_zh` | 否 | `"做某事"` |
| `usage` | ✅ | `"my-pkg;do-something,<param>"` |
| `usage_zh` | 否 | `"我的包;做某事,<参数>"` |
| `description` | ✅ | 英文一句话 |
| `description_zh` | 否 | 中文一句话 |
| `params` | 建议 | `["param"]` |
| `params_desc` | 建议 | `{"param": "说明"}` |
| `outputs` | 建议 | `["field1"]` |
| `estimated_time` | 否 | `"30s"` |
| `estimated_time_note` | 否 | 预估时间说明 |

### 2.5 反例

| ❌ 错误 | ✅ 正确 |
|---------|---------|
| `"type": "api"` | `"type": "native"` |
| handler 返回 JSON 字符串 | handler 返回 dict/object |
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

handler 返回 **dict/object**（不是 JSON 字符串），运行时将其直接放入响应信封的 `rst_data`。协议不约束 `rst_data` 的内部结构——包作者自行决定返回格式：

```json
// 示例一：简单结果
{"result": "2026-01-31"}

// 示例二：带状态标记（适用于不想被 path 处理的包）
{"status": "ok", "result": "...", "detail": "..."}
{"status": "error", "reason": "..."}
```

**约束**：
- 返回 dict/object，不返回 JSON 字符串
- 不嵌套 `data` 层
- 错误信息可读、不泄露密钥或堆栈

> `rst_err` 是传输层字段（网关/运行时层），handler 不感知也不应设置。
> `{"status": "ok/error", ...}` 是包的**自维护约定**——有些包不想被 path 编排处理，通过自维护 `status` 字段表达边界。这不是协议强制，是包的自由。
