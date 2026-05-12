# text_cli/js — 技能服务模板（Cloudflare Workers）

可被 `server/` 集成端点直接调用的标准指令服务。基于 Cloudflare Workers + D1 构建，支持全球边缘部署。开发者以此模板为骨架，用 `registerHandler` 注册自己的指令处理函数。

---

## 目录结构

```
text_cli/js/
├── src/
│   ├── index.js              # Worker 入口（路由 + 指令分发）
│   ├── parser.js             # 指令文本解析（正则 → ParsedDirective）
│   ├── auth.js               # Service Token 鉴权（D1 多 Token / 单 Token 双模式）
│   ├── registry.js           # registerHandler 注册表 + dispatch 分发
│   ├── schema.js             # Schema 管理（D1 读取 / 静态文件回退）
│   └── handlers/
│       ├── index.js           # 聚合导入所有 handler 模块
│       └── sample.js          # 示例指令（回显 / 问候 / 列表）
├── schema/
│   └── text_cli_schema.json   # 静态 Schema 源文件
├── migrations/
│   └── 0001_init.sql          # D1 数据库迁移脚本（仅 D1 模式使用）
├── scripts/
│   └── seed-directives.js     # 将静态 Schema 导入 D1
├── test/
│   ├── parser.test.js
│   └── registry.test.js
├── wrangler.toml
├── package.json
└── vitest.config.js
```

---

## 核心模块职责

| 模块 | 职责 |
|:---|:---|
| `src/parser.js` | 将 `指令:领域;动作,参数...` 解析为结构化对象，含格式校验和长度/参数上限 |
| `src/registry.js` | `registerHandler(domain, action, fn)` 注册 + `dispatch()` 路由分发 |
| `src/auth.js` | D1 多 Token + 配额模式（有数据库时）/ 单 Token 模式（回退到环境变量） |
| `src/schema.js` | 从 D1 读取指令 Schema，无 D1 时回退到静态 JSON 文件 |
| `src/handlers/` | 新增指令只需在此目录加 `.js` 文件并用 `registerHandler` 注册——`index.js` 聚合导入 |

---

## 快速启动

```bash
cd text_cli/js
npm install
wrangler dev
```

启动后访问：
- `GET /health` — 查看已注册指令
- `GET /text_cli_schema.json` — 查看 Schema
- `POST /cli/text_cli` — 发送文本指令

## 注册新指令

```javascript
// src/handlers/my_handler.js
import { registerHandler } from '../registry.js';

registerHandler('基础应用', '天气查询', (params) => {
  const city = params[0] || '默认城市';
  return `${city}天气: 晴, 22°C`;
});
```

然后在 `src/handlers/index.js` 中导入：

```javascript
import './sample.js';
import './my_handler.js';
```

### 鉴权

**精简模式**（无 D1）：设置环境变量 `SERVICE_TOKEN`，调用方需携带：

```
Service-token: your-service-token
```

**D1 模式**：通过 `tokens` 表管理多租户 Token + 配额，Token 以 SHA-256 哈希存储。

### 部署

```bash
wrangler deploy
```

部署前需创建 D1 数据库并执行迁移（详见 `docs/CN/Building_text-cli_guide_CN.md` §9.8）。

### 测试

```bash
npm test
```
