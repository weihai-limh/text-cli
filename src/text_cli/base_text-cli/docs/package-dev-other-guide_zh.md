# 旁路运行时指令包开发指南

> 面向需要在非标准运行时上部署指令包的开发者。
> 制作方法见 [package-dev-guide_zh.md](package-dev-guide_zh.md)；schema 规范见 [package-publish-guide_zh.md](package-publish-guide_zh.md)。

---

## 0. 旁路运行时

text-cli 指令包默认通过 `text-cli;install` 部署到标准运行时。但当包需要独立弹性环境、公网可达端点、或云平台特有的触发/伸缩能力时，可以使用**旁路运行时**——不走 install 管线，由独立网关承载。

| | 标准运行时 | 旁路运行时 |
|---|---|---|
| 部署 | `text-cli;install` / `co-install` | 云函数部署（如 CloudBase SCF） |
| handler 注册 | handler_inits + manifest | 网关注册表 |
| schema.json | 相同 | 相同（部分平台有额外字段要求） |

当前实例：**CloudBase SCF**。其他旁路运行时（Cloudflare Workers 等）可参照扩展。

---

## 1. CloudBase 云函数指令包

CloudBase SCF 是腾讯云的无服务器函数平台。指令包部署为云函数后，经网关对外提供 text-cli 协议服务。

### 1.1 文件结构

```
<package-id>/
├── schema.json          ← 必须。type:native, runtime:node
├── index.js             ← 云函数入口（exports.main）
├── instructions/        ← 各 action 的 handler
│   ├── action_a.js
│   └── action_b.js
├── package.json         ← 云函数依赖（如 wx-server-sdk）
└── README.md            ← 建议
```

与标准 install 包的关键差异：
- **无** `handler.py` / `handler_inits` / `text_cli_modules` —— 这些是标准管线的特质
- `index.js` 是云函数入口，分发靠 `instructions/` 目录 + `INSTRUCTIONS` map
- `package.json` 的依赖由云函数构建时安装

### 1.2 schema.json

```json
{
  "id": "web-utils",
  "type": "native",
  "name": "Web Utils",
  "name_zh": "Web工具",
  "runtime": "node",
  "version": "1.0.0",
  "category": "utils",
  "locales": ["zh", "en"],
  "trust": "internal",
  "description": "Web utilities.",
  "description_zh": "Web工具。",
  "directives": [
    {
      "domain": "web-utils",
      "domain_zh": "Web工具",
      "action": "get_public_ip",
      "action_zh": "获取公网IP",
      "usage": "web-utils;get_public_ip",
      "usage_zh": "Web工具;获取公网IP",
      "description": "Get the public IP.",
      "description_zh": "获取当前公网 IP 地址",
      "params": [
        {"name": "format", "required": false, "description": "Output format"}
      ],
      "params_desc": { "format": "json or text" },
      "outputs": ["ip"]
    }
  ]
}
```

**CloudBase 平台额外要求**：

| 字段 | 要求 |
|------|------|
| `trust` | 必须为 `internal` |
| `params` | 必须为对象数组 `[{name, required, description}]`（+ `params_desc`） |

其余字段与 SPEC §4.2 一致。无 `entry` 字段（端点由网关持有）。

### 1.3 入口 index.js

```javascript
const INSTRUCTIONS = {
  'action_a': require('./instructions/action_a'),
  'action_b': require('./instructions/action_b'),
};

exports.main = async (event, context) => {
  // SDK 调用（来自网关的 cloud.callFunction）
  if (!event.httpMethod) {
    if (event.action === 'get_schema') {
      return { schema: require('./schema.json') };
    }
    return await executeInstruction(event.prompt, event);
  }

  // HTTP 调用
  if (event.httpMethod === 'POST') {
    const body = typeof event.body === 'string'
      ? JSON.parse(event.body) : event.body;
    return await executeInstruction(body.prompt, event);
  }

  return errorEnvelope('UNKNOWN_REQUEST');
};

async function executeInstruction(prompt, event) {
  // 解析 "AI:<domain>;<action>,<params>"
  const match = prompt.match(/^AI:\s*([^;]+);\s*([^,]+)(?:,(.*))?$/);
  if (!match) return errorEnvelope('INVALID_PROMPT');

  const domain = match[1].trim();
  const action = match[2].trim();
  const paramsStr = match[3] || '';
  const params = paramsStr ? paramsStr.split(',').map(s => s.trim()) : [];

  const handler = INSTRUCTIONS[action];
  if (!handler) return errorEnvelope('ACTION_NOT_FOUND');

  try {
    return await handler.handler(params, event);
  } catch (error) {
    return errorEnvelope(`EXECUTION_ERROR: ${error.message}`);
  }
}

function errorEnvelope(result) {
  return {
    rst_types: 'text',
    rst_data: { text: JSON.stringify({ status: 'error', result }) },
  };
}
```

**要点**：
- **双模式**：`event.httpMethod` 不存在 → SDK 调用；存在 → HTTP 调用
- **get_schema**：SDK 模式下 `event.action === 'get_schema'` 时返回 schema.json。这是网关发现指令能力的协议端点，不暴露在公网
- **INSTRUCTIONS map**：`action → handler 模块` 的静态映射，替代标准管线的 `@directive` 装饰器

### 1.4 指令 handler

`instructions/<action>.js` 统一格式：

```javascript
exports.handler = async (params, event) => {
  // params: 字符串数组（已拆分好的参数）
  // event: 云函数事件对象（含 _routerEvent 等网关透传字段）

  return {
    rst_types: 'text',
    rst_data: {
      text: JSON.stringify({
        status: 'ok',
        result: '...'
      })
    }
  };
};
```

返回 **text-cli 响应信封**：`{ rst_types, rst_data: { text: JSON.stringify({ status, result }) } }`。成功 `status: "ok"`，失败 `status: "error"`。

### 1.5 注册与发现

CloudBase 包不在标准管线的 handler_inits 中注册。取而代之：

1. **网关路由表**：登记 `domain → 云函数名` 映射
2. **包注册表**：登记包 id，用于 `AI:text-cli;query` 聚合
3. **get_schema**：网关遍历已注册云函数，调用各自的 get_schema 端点，聚合为全量指令清单

新增包时，在网关侧完成以上三项登记即可。

### 1.6 返回信封

所有指令统一返回：

```json
{
  "rst_types": "text",
  "rst_data": {
    "text": "{\"status\":\"ok\",\"result\":\"...\"}"
  }
}
```

业务结果固定在 `result` 字段。错误统一返回 HTTP 200，错误信息在 `rst_data.text` 内。

---

## 2. 其他旁路运行时

> 预留扩展。其他云平台（Cloudflare Workers 等）的指令包部署模式可参照 CloudBase 章节的结构追加。
