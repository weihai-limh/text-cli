# 指令包脚手架转化器指南

> 脚本将既有软件工程制品转化为指令包**起手骨架**——不是代码生成器，是脚手架生成器。
> 完整开发流程见对应的开发指南。

---

## 一、转化脚手架与指令包类型的映射

| 转化脚手架 | 转化器脚本 | 输入 | 产出 | 目标运行时 | 下一步开发指南 |
|-----------|-----------|------|------|-----------|-------------|
| webapi 指令包 | `postman_to_pkg_python.py` | Postman Collection JSON | schema.json + handler.py | Python 标准运行时 | [package-python-dev-guide_zh.md](package-python-dev-guide_zh.md) |
| MCP 桥接包 | `mcp_to_pkg.py` | MCP server（mcporter） | schema.json + service-descriptor.json | Python 标准运行时（MCP） | [package-python-dev-guide_zh.md](package-python-dev-guide_zh.md) |



---

## webapi 指令包（postman_to_pkg_python.py）

### 输入

Postman Collection JSON（v2.1 格式）。脚本解析 collection 中的请求，提取 URL、method、headers、body 等信息，生成对应的指令声明。

### 产出

```
<包名>/
├── schema.json    ← 元数据 + 指令声明（domain/action/usage/params）
└── handler.py     ← 桩代码（函数签名 + @directive 注册，返回 dict）
```

### 拿到脚手架后要补什么

- 填写 `schema.json` 中的 `trust`、`credentials` 等字段
- 在 `handler.py` 桩中实现实际的 API 调用逻辑
- 配置 API key（通过 key_registry，不硬编码）
- 补充降级和错误处理

---


## MCP 桥接包（mcp_to_pkg.py）

### 输入

已配置的 MCP server（通过 `mcporter list --json` 获取 tool 清单）。脚本将 MCP tools 映射为 text-cli 指令声明。

### 产出

```
<包名>/
├── schema.json              ← 元数据 + 指令声明（runtime: "mcp"）
└── service-descriptor.json  ← mcporter 路由映射（server → tool 对应关系）
```

**不生成 handler.py**——MCP 桥接包是零代码桥接，调用链为 text-cli 指令 → mcp_dispatch → mcporter → MCP server。

### 前置条件

安装 MCP 桥接包之前，必须先在 mcporter 中配置好对应的 server 连接。安装器会调用 `mcporter list <server_name>` 验证——如果 server 未配置，安装会失败。

### 拿到脚手架后要补什么

- 验证 `service-descriptor.json` 中的 tool 映射是否完整
- 在 mcporter 中配置 server 连接
- 安装后验证调用链通达
