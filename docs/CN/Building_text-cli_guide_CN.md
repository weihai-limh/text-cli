# 文本服务构建指南

text-cli 让能力和 AI 说同一种语言。

你写一条指令 → AI 自动发现 → 组合成技能 → 对外发布。
整个过程自闭合——不需要人类在中间翻译、配置、路由。

本指南带你从最简单的第一步走到完全自控的终点：

| 章 | 你会得到 |
|----|---------|
| §1 协议基础 | 理解 text-cli 的请求/响应格式 |
| §2 快速开始 | 30 行代码，写一个指令包，AI 就能调用 |
| §3 编排能力 | 把多个指令串成技能，一键发布为可调用的 `skill;*` |
| §4+ 进阶 | 自建完整服务、独立部署、完全控制权 |

**text-cli 生态支持两种参与方式：**

- **构建指令包**（推荐入门）—— 写 `schema.json` + handler → `text-cli;install` → 立即可用。适合：你有现成的 API/库/脚本，想快速接入。

- **自建独立服务** —— 完整的 HTTP 服务，自定义鉴权和部署。适合：你需要私有部署、非标准协议扩展、完全控制权。完整源码在 `progressive_deploy/A3-service/`，开箱即用。

本指南先教你最简单的路径，再逐步深入。每一章的代码都可以直接跑——它们来自 text-cli 仓库里正在运行的实现。

---

## 1. 服务规范

### 1.1 请求约定

text-cli 指令以 HTTP POST 发出。请求体固定为 JSON：

```json
{
  "prompt": "指令:你的领域;你的动作,参数1,参数2,..."
}
```

**支持的指令前缀**（等价）：`指令:`、`AI:`、`directive:`。

**请求头中可能携带**：
- `Authorization: Bearer <Access Token>`（由集成端点发放，标识调用者）
- `Service-token: <你与调用者私下约定的 Token>`（用于你端的鉴权 / 计费）

### 1.2 响应约定

返回体为 JSON：

```json
{
  "rst_types": "text",
  "rst_data": {
    "text": "你的结果"
  }
}
```

- `rst_types`：固定为 `"text"`（当前协议版本 v1）
- `rst_data.text`：实际返回内容——自然语言、JSON、URL、Base64 均可
- 错误响应可加 `rst_err` 字段标识错误类型（如 `"path_denied"`、`"unknown_instruction"`）

---

## 2. 快速开始：构建指令包

指令包是最简单的 text-cli 接入方式。你不需要建 HTTP 服务、不需要写路由、不需要配置鉴权——只需要两个文件。

### 2.1 五分钟体验

**第一步：创建包目录**

```
my-weather/
├── schema.json      ← 指令声明（domain/action/usage/params）
└── weather.py       ← handler：接收参数 → 返回结果
```

**第二步：写 schema.json**

```json
{
  "id": "my-weather",
  "name": "My Weather",
  "name_cn": "我的天气",
  "runtime": "python",
  "description": "Query weather for any city",
  "description_cn": "查询任意城市天气",
  "directives": [
    {
      "domain": "weather",
      "domain_cn": "天气",
      "action": "query",
      "action_cn": "查询",
      "usage": "weather;query,<city>",
      "usage_cn": "天气;查询,<城市>",
      "description": "Get current weather for a city",
      "description_cn": "获取城市当前天气"
    }
  ]
}
```

**第三步：写 handler**

```python
# weather.py
from core.registry import directive

@directive("weather", "query")
@directive("天气", "查询")
def weather_query(params: list[str]) -> str:
    city = params[0] if params else "北京"
    # 调用你的 API 或数据库
    return f"{city}: 晴, 22°C"
```

**第四步：安装**

```bash
# 把包放到注册源目录后，通过指令安装：
AI:text-cli;install,my-weather
```

AI 立刻可以调用：

```
AI:天气;查询,威海
→ "威海: 晴, 18°C"
```

`AI:text-cli;query` 会自动发现这条新指令——不需要你手动注册任何 Schema 端点。

### 2.2 四种 runtime

| runtime | 包内容 | 适合场景 | 执行方式 |
|---------|--------|---------|---------|
| `python` | `handler.py` + `schema.json` [+ `requirements.txt`] | 有 Python 库依赖 | 直接函数调用 |
| `mcp` | `schema.json` + `service-descriptor.json` | 已有 MCP server，想接入 text-cli | mcporter 路由 |
| `node` | `handler.js` + `schema.json` | 有 Node.js 依赖、浏览器端代码 | subprocess (js_bridge) |
| `cmd` | `schema.json` + `whitelist.json` | 系统 CLI 工具（git, docker, openclaw） | subprocess (whitelist) |

选 `python` 如果你只需要一个 handler 函数。选 `mcp` 如果你已有 MCP server 在跑。选 `node` 如果你的代码依赖 Node 生态。选 `cmd` 如果你想给 CLI 工具套上指令层。

### 2.3 平台管理指令

安装后的包由 text-cli 平台统一管理：

```
text-cli;query                  → 查看所有已安装指令
text-cli;install,<包名>          → 安装能力包
text-cli;uninstall,<包名>        → 卸载能力包（系统域保护，不可卸载 text-cli 自身）
```

卸载时自动移除 handler 和 schema 文件，保留审计日志。

---

## 3. 编排能力：从单条指令到复合技能

单条指令是工具。把多条指令串起来是技能。text-cli 的路径引擎让你用声明式 JSON 定义复合流水线。

### 3.1 路径声明

创建一个路径 JSON 文件：

```json
{
  "id": "city_insight",
  "name": "城市洞察",
  "name_en": "City Insight",
  "version": "1.0.0",
  "type": "skill",
  "mode": "toolchain",
  "description": "查天气 → AI 推理穿衣建议",
  "input_schema": {"type": "string"},
  "output_schema": {"type": "text"},
  "requires": ["weather;query", "AI;reasoning"],
  "steps": [
    {"directive": "weather;query,${input}", "output_as": "weather"},
    {"directive": "AI;reasoning,根据天气${weather}给出穿衣建议,fast", "output_as": "advice"}
  ]
}
```

注册路径声明：

```
AI:text-cli;path,/path/to/city_insight.json,--register
→ 返回: "路径已注册: 城市洞察 (v1.0.0)"
```

变量 `${input}` 取初始输入，`${weather}` 取上一步输出。步骤按序执行，后一步自动引用前一步结果。

### 3.2 发布为技能

```bash
AI:text-cli;pro,city_insight,domain=skill,action=城市洞察
→ 返回: "✅ 发布成功: skill;城市洞察"
```

发布后，任何人（包括 AI）都可以用一条指令调用整个流水线：

```
AI:skill;城市洞察,威海
→ 查天气 → AI 推理 → 穿衣建议
```

技能内部步骤对调用者透明——调用者不需要知道它由几条指令组成。

### 3.3 对外暴露

已发布的技能默认只在内部可见（`text-cli;query`）。要让外部消费者发现和调用，在 `skills_exposure.json` 中配置：

```json
{
  "city_insight": {
    "visibility": "public",
    "description_public": "输入城市名，返回天气 + 穿衣建议",
    "rate_limit": {"per_hour": 20}
  }
}
```

暴露后：

```
GET /text-cli/skills                    → 列出所有公开技能
GET /text-cli/skills/city_insight       → 查看详情（含步骤）
POST /text-cli/skills/city_insight      → 鉴权后执行
```

三种可见度：`public`（任意调用）、`restricted`（需 scope）、`internal`（仅内部 query 可见，不对外）。

---

如果你需要完整控制权——自定义鉴权、私有部署、非标准协议扩展——以下是完整的自建服务指南。完整源码在 `progressive_deploy/A3-service/`，可直接 clone 运行。

如果你需要完整控制权——自定义鉴权、私有部署、非标准协议扩展——以下是完整的自建服务指南。完整源码在 `progressive_deploy/A3-service/`，可直接 clone 运行。

我们以一个 **"室内温湿度查询"** 技能为例，假设你有一个传感器数据库，要提供一条指令：`指令:我的传感器;温湿度,房间ID`。

## 4. 自建独立服务

我们以一个 **"室内温湿度查询"** 技能为例,假设你有一个传感器数据库,要提供一条指令:`指令:我的传感器;温湿度,房间ID`。

### 6.1 Node.js 版(Express)

**项目初始化**

```bash
mkdir my-skill-js && cd my-skill-js
npm init -y
npm install express
```

**`server.js` 完整代码**

```javascript
const express = require('express');
const app = express();
app.use(express.json());

// ────────────────────────────────────────────
// 核心业务逻辑(模拟传感器数据库)
// ────────────────────────────────────────────
function getRoomClimate(roomId) {
  const db = {
    '101': { temp: 24.5, humidity: 60 },
    '102': { temp: 26.1, humidity: 55 },
    'default': { temp: 25.0, humidity: 58 }
  };
  const data = db[roomId] || db['default'];
  return `房间${roomId}: 温度${data.temp}°C,湿度${data.humidity}%`;
}

// ────────────────────────────────────────────
// 指令解析器(协议核心)
// 格式: 指令:<领域>;<动作>,<参数1>,<参数2>,...
// ────────────────────────────────────────────
function parseDirective(prompt) {
  const body = prompt.replace(/^指令[::]/, '').trim();
  if (!body.includes(';')) throw new Error('指令格式错误:缺少分号分隔符');

  const [domainAndAction, ...params] = body.split(',');
  const [domain, action] = domainAndAction.split(';');

  return {
    domain: domain.trim(),
    action: action.trim(),
    params: params.map(p => p.trim())
  };
}

// ────────────────────────────────────────────
// POST /cli/text_cli  主入口
// ────────────────────────────────────────────
app.post('/cli/text_cli', (req, res) => {
  try {
    const { prompt } = req.body;
    if (!prompt) {
      return res.status(400).json({
        rst_types: 'text',
        rst_data: { text: '错误:缺少 prompt 字段' }
      });
    }

    const { domain, action, params } = parseDirective(prompt);
    console.log(`收到指令: ${domain};${action}, 参数: ${params}`);

    let resultText = '';

    // 路由分发
    if (domain === '我的传感器' && action === '温湿度') {
      if (params.length < 1) throw new Error('参数不足:需要房间ID');
      resultText = getRoomClimate(params[0]);
    } else if (domain === '我的传感器' && action === '列表') {
      resultText = '可用房间: 101, 102';
    } else {
      resultText = `未找到匹配的指令: ${domain};${action}`;
    }

    res.json({
      rst_types: 'text',
      rst_data: { text: resultText }
    });
  } catch (e) {
    res.json({
      rst_types: 'text',
      rst_data: { text: `指令执行失败: ${e.message}` }
    });
  }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`文本指令服务运行在 http://localhost:${PORT}`);
});
```

**本地测试**

```bash
node server.js
```

另开终端:

```bash
curl -X POST http://localhost:3000/cli/text_cli \
  -H "Content-Type: application/json" \
  -d '{"prompt":"指令:我的传感器;温湿度,101"}'
```

返回:

```json
{
  "rst_types": "text",
  "rst_data": {
    "text": "房间101: 温度24.5°C,湿度60%"
  }
}
```

---

### 6.2 Python 版(FastAPI)- 模块化模板

> **完整参考实现**:`progressive_deploy/A3-service/`(仓库内可直接运行的完整模板)

**项目结构**

```
progressive_deploy/A3-service/
├── core/
│   ├── __init__.py
│   ├── parser.py        # 指令解析器(正则 + dataclass)
│   ├── auth.py          # Service Token 鉴权
│   ├── registry.py      # 指令注册表(装饰器模式)
│   └── response.py      # 标准响应构建
├── handlers/
│   ├── __init__.py      # 自动发现并导入所有 handler 模块
│   └── sample.py        # 示例指令 handler
├── config/
│   └── text_cli_schema.json
├── main.py              # FastAPI 入口
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

**项目初始化**

```bash
cd progressive_deploy/A3-service
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

#### 4.2.1 指令解析器 `core/parser.py`

使用正则匹配 `指令:<领域>;<动作>,<参数>` 格式,返回结构化的 `ParsedDirective`:

```python
import re
from dataclasses import dataclass

DIRECTIVE_PATTERN = re.compile(
    r"^\s*指令[::]([^;]+);([^,]+)(?:,(.+))?\s*$"
)

MAX_DIRECTIVE_LENGTH = 512
MAX_PARAMS = 20


@dataclass
class ParsedDirective:
    domain: str
    action: str
    params: list[str]
    raw: str

    @property
    def directive_key(self) -> str:
        return f"指令:{self.domain};{self.action}"


class DirectiveParseError(Exception):
    def __init__(self, message: str, code: str = "INVALID_DIRECTIVE_FORMAT"):
        self.message = message
        self.code = code
        super().__init__(message)


def parse_directive(prompt: str | None) -> ParsedDirective:
    if not prompt or not prompt.strip():
        raise DirectiveParseError("prompt is required")

    prompt = prompt.strip()

    if len(prompt) > MAX_DIRECTIVE_LENGTH:
        raise DirectiveParseError(
            f"directive exceeds max length ({MAX_DIRECTIVE_LENGTH})"
        )

    match = DIRECTIVE_PATTERN.match(prompt)
    if not match:
        raise DirectiveParseError(f"invalid directive format: {prompt}")

    domain = match.group(1).strip()
    action = match.group(2).strip()
    raw_params = match.group(3)

    params: list[str] = []
    if raw_params:
        for p in raw_params.split(","):
            p = p.strip()
            if p:
                params.append(p)

    if len(params) > MAX_PARAMS:
        raise DirectiveParseError(
            f"too many parameters ({len(params)}), max {MAX_PARAMS}"
        )

    if not domain:
        raise DirectiveParseError("domain is empty")
    if not action:
        raise DirectiveParseError("action is empty")

    return ParsedDirective(
        domain=domain,
        action=action,
        params=params,
        raw=prompt,
    )
```

#### 4.2.2 标准响应 `core/response.py`

```python
def ok(text: str) -> dict:
    return {"rst_types": "text", "rst_data": {"text": text}}


def error(text: str) -> dict:
    return {"rst_types": "text", "rst_data": {"text": f"指令执行失败: {text}"}}
```

#### 4.2.3 指令注册表 `core/registry.py`

使用装饰器模式自动注册指令 handler,无需手动维护 if/elif 路由:

```python
import logging
from typing import Callable

logger = logging.getLogger(__name__)

_registry: dict[str, dict[str, Callable]] = {}


def directive(domain: str, action: str):
    def decorator(func: Callable):
        if domain not in _registry:
            _registry[domain] = {}
        _registry[domain][action] = func
        logger.info("指令已注册: %s;%s -> %s", domain, action, func.__name__)
        return func
    return decorator


def dispatch(domain: str, action: str, params: list[str]) -> str:
    actions = _registry.get(domain)
    if not actions:
        return f"未找到匹配的指令: {domain};{action}"

    handler = actions.get(action)
    if not handler:
        return f"未找到匹配的指令: {domain};{action}"

    return handler(params)


def get_registered_directives() -> dict[str, list[str]]:
    return {
        domain: list(actions.keys())
        for domain, actions in _registry.items()
    }
```

#### 4.2.4 Handler 自动发现 `handlers/__init__.py`

启动时自动扫描 `handlers/` 目录下所有模块,触发 `@directive` 装饰器注册:

```python
import importlib
import pkgutil
import pathlib

package_dir = pathlib.Path(__file__).parent
for _, module_name, _ in pkgutil.iter_modules([str(package_dir)]):
    if module_name != "__init__":
        importlib.import_module(f".{module_name}", package=__name__)
```

#### 4.2.5 示例 Handler `handlers/sample.py`

> **添加新指令只需在此目录下新建 `.py` 文件,用 `@directive` 装饰器注册即可,无需修改任何其他文件。**

```python
from core.registry import directive


@directive("示例领域", "回显")
def echo(params: list[str]) -> str:
    return f"回显结果: {', '.join(params)}" if params else "回显结果: (无参数)"


@directive("示例领域", "问候")
def greet(params: list[str]) -> str:
    name = params[0] if params else "世界"
    return f"你好, {name}!"


@directive("示例领域", "列表")
def list_items(params: list[str]) -> str:
    return "示例指令列表:\n- 回显: 回显参数\n- 问候: 问候指定名称\n- 列表: 显示此列表"
```

#### 4.2.6 主入口 `main.py`

```python
import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from core.parser import parse_directive, DirectiveParseError
from core.auth import verify_service_token
from core.registry import dispatch, get_registered_directives
from core.response import ok, error

LOG_LEVEL = os.getenv("LOG_LEVEL", "info").upper()
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))
logger = logging.getLogger(__name__)

SCHEMA_PATH = os.getenv(
    "SCHEMA_PATH",
    str(project_root / "config" / "text_cli_schema.json"),
)

_schema: dict[str, dict] = {}


def _load_schema():
    global _schema
    if not os.path.exists(SCHEMA_PATH):
        logger.warning("Schema not found: %s", SCHEMA_PATH)
        _schema = {}
        return
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        _schema = json.load(f)
    logger.info("Loaded %d directives from %s", len(_schema), SCHEMA_PATH)


@asynccontextmanager
async def lifespan(app: FastAPI):
    import handlers  # noqa: F401 - 触发自动注册
    _load_schema()
    registered = get_registered_directives()
    logger.info("Registered handlers: %s", registered)
    yield
    logger.info("Shutting down.")


app = FastAPI(
    title="text-cli 示例指令服务",
    description="text-cli 标准指令服务模板,可被 Service_endpoint 集成",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/text_cli_schema.json")
async def get_schema():
    return JSONResponse(content=_schema)


@app.get("/health")
async def health():
    directives = get_registered_directives()
    return {"status": "ok", "directives": directives}


@app.post("/cli/text_cli")
async def handle_directive(request: Request):
    service_token = request.headers.get("Service-token")
    auth = verify_service_token(service_token)
    if not auth.allowed:
        return JSONResponse(
            status_code=403,
            content=error(auth.message),
        )

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content=error("请求体不是有效 JSON"),
        )

    prompt = body.get("prompt")
    if not prompt:
        return JSONResponse(
            status_code=400,
            content=error("缺少 prompt 字段"),
        )

    try:
        parsed = parse_directive(prompt)
    except DirectiveParseError as e:
        return JSONResponse(
            status_code=400,
            content=error(f"{e.code}: {e.message}"),
        )

    logger.info(
        "收到指令: %s;%s, 参数: %s",
        parsed.domain, parsed.action, parsed.params,
    )

    result = dispatch(parsed.domain, parsed.action, parsed.params)

    return ok(result)


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
```

**本地测试**

```bash
cd progressive_deploy/A3-service
python main.py
```

另开终端测试三个端点:

```bash
# 健康检查
curl http://localhost:8000/health

# 执行指令
curl -X POST http://localhost:8000/cli/text_cli \
  -H "Content-Type: application/json" \
  -d '{"prompt":"AI:示例领域;回显,hello"}'

# 获取 Schema(Agent 发现用)
curl http://localhost:8000/text_cli_schema.json
```

返回:

```json
{"rst_types": "text", "rst_data": {"text": "回显结果: hello"}}
```

---

## 5. Service Token 鉴权

生产环境中,你不可能允许任何人无限调用。`text-cli` 集成端点在转发请求时,会**原样透传**调用方携带的 `Service-token` 头,你只需在自己服务中校验即可。

### 5.1 Node.js 版鉴权中间件

```javascript
// 定义你的客户端 Token 库
const VALID_TOKENS = {
  'client-abc-123': { name: '张三', quota: 1000, used: 0 },
  'client-def-456': { name: '李四', quota: 500,  used: 0 }
};

function authenticate(req, res, next) {
  const serviceToken = req.headers['service-token'];
  if (!serviceToken || !VALID_TOKENS[serviceToken]) {
    return res.status(403).json({
      rst_types: 'text',
      rst_data: { text: '无权访问:Service-token 缺失或无效' }
    });
  }
  req.clientInfo = VALID_TOKENS[serviceToken];
  next();
}

// 应用到路由
app.post('/cli/text_cli', authenticate, (req, res) => {
  // ......原有逻辑不变
});
```

### 5.2 Python 版鉴权(`core/auth.py`)

实际模板使用单 Token 模式,通过环境变量 `SERVICE_TOKEN` 配置。未设置时自动放行(方便开发):

```python
import os
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

SERVICE_TOKEN = os.getenv("SERVICE_TOKEN", "")


@dataclass
class AuthResult:
    allowed: bool
    client_name: str
    message: str


def verify_service_token(token: str | None) -> AuthResult:
    if not SERVICE_TOKEN:
        return AuthResult(allowed=True, client_name="anonymous", message="")

    if not token:
        return AuthResult(
            allowed=False,
            client_name="",
            message="Service-token 缺失",
        )

    clean = token.strip()

    if clean != SERVICE_TOKEN:
        logger.warning("Service-token 验证失败: prefix=%s", clean[:8])
        return AuthResult(
            allowed=False,
            client_name="",
            message="Service-token 无效",
        )

    return AuthResult(allowed=True, client_name="authenticated", message="")
```

在 `main.py` 中直接调用:

```python
@app.post("/cli/text_cli")
async def handle_directive(request: Request):
    service_token = request.headers.get("Service-token")
    auth = verify_service_token(service_token)
    if not auth.allowed:
        return JSONResponse(status_code=403, content=error(auth.message))
    # ......原有逻辑不变
```

**部署时设置 Token**:

```bash
# 环境变量方式
export SERVICE_TOKEN="your-secret-token"

# 或在 docker-compose.yml 中
environment:
  - SERVICE_TOKEN=your-secret-token
```

**与调用方协商 Service Token**
你(服务提供者)和调用方私下约定一个 Token,并告知对方:
> "每次调用 `/cli/text_cli` 时,请在请求头中加入 `Service-token: <约定的Token>`,集成端点会原样转发。"

---

## 6. 让 Agent 发现你的指令

如果你通过 §2的指令包方式接入,指令会自动出现在 `text-cli;query` 中——不需要额外配置。

如果你通过自建服务方式接入，你有两种发现机制：

- **`text-cli;query`（推荐）**——如果你在服务中实现了 `schema_query` handler（参考 `progressive_deploy/A3-service/handlers/schema_query.py`），Agent 可以通过元指令动态获取全部已安装指令。这是最完整、最实时的发现方式。

- **`text_cli_schema.json` 端点（备用）**——暴露一个 GET 端点或静态文件，描述你提供的指令元数据。适合不需要动态发现、指令集固定的场景。

### 6.1 Schema 条目示例

```json
{
  "my_sensor_temp": {
    "id": "my_sensor_temp",
    "name": "室内温湿度查询",
    "category": "我的传感器",
    "description": "根据房间ID返回当前温度和湿度",
    "directive": "指令:我的传感器;温湿度",
    "parameters": [
      {"name": "roomId", "type": "string", "examples": ["101"]}
    ],
    "prompt_template": "指令:我的传感器;温湿度,{roomId}",
    "trigger_keywords": ["温度", "湿度", "传感器", "房间温湿度"],
    "response_type": "text",
    "response_example": {
      "rst_types": "text",
      "rst_data": { "text": "房间101: 温度24.5°C,湿度60%" }
    }
  },
  "my_sensor_list": {
    "id": "my_sensor_list",
    "name": "传感器房间列表",
    "category": "我的传感器",
    "description": "返回所有可查询的房间ID",
    "directive": "指令:我的传感器;列表",
    "parameters": [],
    "prompt_template": "指令:我的传感器;列表",
    "trigger_keywords": ["房间列表", "有哪些房间"],
    "response_type": "text",
    "response_example": {
      "rst_types": "text",
      "rst_data": { "text": "可用房间: 101, 102" }
    }
  }
}
```

### 6.2 Schema 暴露方式

实际模板通过 GET 端点动态返回 Schema(从 `config/text_cli_schema.json` 加载),而非静态文件挂载:

```python
# main.py 中
@app.get("/text_cli_schema.json")
async def get_schema():
    return JSONResponse(content=_schema)
```

Schema 在 `lifespan` 启动时自动加载,支持通过 `SCHEMA_PATH` 环境变量自定义路径:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    import handlers  # 触发自动注册
    _load_schema()
    registered = get_registered_directives()
    logger.info("Registered handlers: %s", registered)
    yield
```

也可以单独托管:放在 `https://your-cdn.com/text_cli_schema.json`,只要可公开访问即可。

Agent 会通过 `fetch_available_directives` 工具(参考集成文档)下载该文件,自动提取指令。

---

## 7. 部署上线

### 5.1 平台建议

- **Node.js**:Railway、Render、Heroku、阿里云 ECS
- **Python**:Deta Space、Fly.io、阿里云函数计算 + API 网关(需适配 WSGI/ASGI)

无论哪种平台,核心步骤一致:
1. 确保服务监听在 `0.0.0.0`,平台自动分配域名。
2. 开启 HTTPS(云平台通常自动提供)。
3. 将你的服务地址告知调用方(如 `https://my-skill.example.com`)。
4. 私下交换 `Service Token`。

### 5.2 Docker 部署(Python 版)

模板项目自带 `Dockerfile` 和 `docker-compose.yml`,可一键启动:

**Dockerfile**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**docker-compose.yml**

```yaml
version: '3.8'

services:
  text-cli-skill:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./config:/app/config
    environment:
      - SERVICE_TOKEN=your-service-token
      - LOG_LEVEL=info
    restart: unless-stopped
```

启动:

```bash
cd progressive_deploy/A3-service
docker compose up -d
```

### 5.3 环境变量汇总

| 变量 | 必填 | 默认值 | 说明 |
|:---|:---|:---|:---|
| `SERVICE_TOKEN` | 否 | 空(放行) | Service Token 鉴权,未设置时跳过校验 |
| `SCHEMA_PATH` | 否 | `config/text_cli_schema.json` | Schema 文件路径 |
| `PORT` | 否 | `8000` | 监听端口 |
| `LOG_LEVEL` | 否 | `info` | 日志级别(debug/info/warning/error) |

### 5.4 与集成端点对接

如果你希望复用 `dev1.agentbot.space` 等公共端点,则无需自建代理,调用方直接通过公共端点转发。否则,你也可自己部署集成端点(参考 `server/python/`),自行控制全局鉴权与路由。

---

## 8. 高级技巧

### 8.1 路径编排（复合指令）

如果你已在服务中部署了 `text_cli_path` handler，你可以用声明式 JSON 把多个指令串成流水线。详见 §3。

### 8.2 异步任务

### 6.1 异步任务(长时处理)

如果你的指令需要生成视频、复杂计算等,可以立即返回一个 `taskId`,然后提供一条"任务查询"指令。

**响应示例**:

```json
{
  "rst_types": "text",
  "rst_data": {
    "text": "任务已提交,taskId: abc-123,请稍后查询"
  }
}
```

在 `text_cli_schema.json` 中添加一条任务查询指令:

```json
{
  "task_query": {
    "id": "task_query",
    "name": "任务查询",
    "category": "我的传感器",
    "description": "查询异步任务的结果",
    "directive": "指令:我的传感器;任务查询",
    "parameters": [
      {"name": "taskId", "type": "string"}
    ],
    "prompt_template": "指令:我的传感器;任务查询,{taskId}",
    "trigger_keywords": ["任务", "查询结果"],
    "response_type": "text"
  }
}
```

这与 `text-cli` 官方预置的 `任务查询` 指令模式一致。

### 6.2 多领域指令共存(装饰器注册)

实际模板使用 `@directive` 装饰器自动注册,无需手动维护路由表。新增指令只需在 `handlers/` 目录下新建文件:

```python
# handlers/weather.py - 天气查询 handler
from core.registry import directive


@directive("基础服务", "天气查询")
def weather_query(params: list[str]) -> str:
    city = params[1] if len(params) > 1 else "威海"
    return f"{city}明天天气: 23°C, 多云"


@directive("我的传感器", "温湿度")
def get_room_climate(params: list[str]) -> str:
    room_id = params[0] if params else "101"
    return f"房间{room_id}: 温度24.5°C,湿度60%"
```

`handlers/__init__.py` 会自动扫描并导入所有模块,`@directive` 装饰器将函数注册到全局注册表。`dispatch()` 根据 `domain` + `action` 自动路由到对应 handler:

```
指令:基础服务;天气查询,明天,威海  →  weather_query(["明天", "威海"])
指令:我的传感器;温湿度,101        →  get_room_climate(["101"])
```

### 6.3 错误处理与日志

- 所有异常都必须捕获并返回 `rst_types: "text"` 格式,避免调用方解析崩溃。
- 记录每条指令的调用日志(domain/action/参数/耗时/调用方),便于计费和优化。

### 6.4 性能优化

- **冷启动优化**:对于 Serverless 部署,设置最小保活实例或使用 `text-cli` 官方的 Cron 预热机制。
- **缓存**:在服务前加一层缓存(如 Redis),对相同参数的指令直接返回缓存结果。
- **异步队列**:对于高并发或长任务,引入消息队列(如 Bull、Celery)避免阻塞。

---

## 9. 安全提醒

- **保护你的知识产权**：指令服务对外完全"黑箱"，调用方只能看到输入参数和输出文本，无法获取任何代码、提示词或数据源细节。
- **鉴权严防**：务必校验 `Service-token`，避免未经授权的调用。
- **输入验证**：对所有参数做白名单 / 类型校验，防止注入攻击（虽然协议设计天然隔离，但仍需谨慎）。

---

## 10. 通过 Agent 辅助实现

如果你不是开发者，或不想从头编写服务端代码，可以使用仓库中的 **`text_cli/agent/` 工具包**，通过 Agent 辅助完成指令的构建与调用。

### 10.1 整体架构

`agent/` 下按角色分为两大模块：

```
text_cli/agent/
├── call/          ← 消费者：Agent 如何调用已有指令
│   ├── python/    ← Python SDK + Skill 技能封装
│   ├── shell/     ← 最简 curl 调用
│   └── nocode/    ← Agent 技能定义模板（System Prompt + 工具描述）
└── cli/           ← 生产者：Agent 如何发布自身能力为指令
    ├── python/    ← @register 装饰器 + 轻量 HTTP 服务
    └── nocode/    ← Markdown → 指令 转化（非开发者路径）
```

### 10.2 非代码模式：Markdown → 指令（nocode）

这是 Markdown2Text-cli 理念的 Agent 侧实现。非开发者只需写一份结构化 Markdown，Agent 自动将其转化为可调用的 text-cli 指令。

**第一步：编写经验文档**

按固定结构写 Markdown（参考 `agent/CN/cli/nocode/盆栽急救手册.md`）：

```markdown
# 你的经验标题

## 指令定义
- 领域: 你的领域名
- 动作: 你的动作名
- 触发词: 关键词1, 关键词2, ...
- 参数: 参数1, 参数2

## 经验内容

### 分类1
#### 场景1
- 说明...
- 处理...
```

**第二步：启动指令服务**

```bash
cd text_cli/agent/CN/cli/nocode
python markdown_converter.py 盆栽急救手册.md
```

**第三步：调用**

```bash
curl -X POST http://localhost:8000/cli/text_cli \
  -H "Content-Type: application/json" \
  -d '{"prompt": "指令:家庭园艺;盆栽急救,绿萝,叶片发黄"}'
```

`markdown_converter.py` 会自动：解析 Markdown → 提取 `## 指令定义` 元数据 → 按 `### 植物` + `#### 症状` 建立检索索引 → 注册为 text-cli 指令处理器 → 启动 HTTP 服务。

完整流程参考 `docs/CN/Markdown2Text-cli_CN.md`。

> 实现代码位于 `text_cli/agent/CN/cli/nocode/`。

### 10.3 Python 模式：@register 装饰器（python）

如果你会写 Python 函数，使用 `@register` 装饰器将既有能力一键注册为指令，零框架依赖：

**安装**

无需安装额外依赖，`cli/python/cli.py` 仅使用 Python 标准库。

**编写 Handler**

在 `cli/python/handlers/` 下新建 `.py` 文件：

```python
from cli.python.cli import register

@register("天气", "查询")
def weather_query(params: list[str]) -> str:
    city = params[0] if params else "北京"
    date = params[1] if len(params) > 1 else "今天"
    # 调用你已有的 API
    return f"{date}{city}: 晴, 22°C"

@register("天气", "预报")
def weather_forecast(params: list[str]) -> str:
    city = params[0] if params else "北京"
    return f"{city}未来三天: 晴转多云, 15-25°C"
```

**启动服务**

```bash
cd text_cli/agent/cli/python
python cli.py
```

服务启动后自动：扫描 `handlers/` 目录 → 注册所有 `@register` 函数 → 生成 `text_cli_schema.json` → 监听 `0.0.0.0:8000`。

**调用**

```bash
curl -X POST http://localhost:8000/cli/text_cli \
  -H "Content-Type: application/json" \
  -d '{"prompt": "指令:天气;查询,威海"}'
# → {"rst_types": "text", "rst_data": {"text": "今天威海: 晴, 22°C"}}
```

### 10.4 Agent 调用指令（call/）

作为消费者，Agent 使用 `call/` 模块调用已有指令：

**Python SDK 调用**

```python
from call.python.call import call_directive

# 单次调用
result = call_directive("指令:天气;查询,威海,明天")
print(result)  # "明天威海: 晴, 15-22°C"
```

**Skill 语义封装**

```python
from call.python.skill import Skill, skill

@skill("天气查询", domain="天气", action="查询")
class WeatherSkill(Skill):
    def format_result(self, raw, params):
        return f"🌤️ {params[0]}: {raw}"

result = WeatherSkill.run("威海", "明天")
```

**最简 Shell 调用**

```bash
export TEXT_CLI_TOKEN="your-token"
./call/shell/call.sh "指令:天气;查询,明天,威海"
```

### 10.5 对比：两种实现路径

| | 开发者路径 (§4-§7) | Agent 辅助路径 (§10) |
|:---|:---|:---|
| **实现位置** | `progressive_deploy/A3-service/` | `text_cli/agent/` |
| **框架** | FastAPI | 标准库（零依赖） |
| **适用** | 独立部署的生产服务 | 快速原型 / Agent 内置能力 |
| **部署** | Docker + 云平台 | 本地一键启动 |
| **Schema** | 手动编写或静态文件 | 自动生成 |
| **鉴权** | Service Token 中间件 | 环境变量注入 |
| **典型用户** | 后端开发者 | AI Agent / 非开发者 |

两种路径生成的服务完全兼容——调用方无需关心指令是由 `server/python` 还是 `agent/cli` 提供的。

---

## 11. Cloudflare Workers + D1 全云部署（Node.js）

> 本章将 §4.1 的 Express 示例重构为 **Cloudflare Workers + D1** 架构,实现零服务器、全球边缘部署。无需 Docker、无需虚拟机,`wrangler deploy` 一次即可上线。

### 11.1 架构总览

```
Cloudflare Edge (全球 300+ 节点)
│
├── Worker (指令服务入口)
│   ├── POST /cli/text_cli           → 解析指令 + 分发 handler + 记录日志
│   ├── GET  /health                 → 健康检查 + 已注册指令列表
│   └── GET  /text_cli_schema.json   → Agent 发现端点(从 D1/KV 读取)
│
├── D1 Database (SQLite at edge)
│   ├── directives 表                → 指令元数据 + Schema 定义
│   ├── tokens 表                    → 多租户 Service Token 管理 + 配额
│   └── usage_logs 表                → 调用日志 + 计费依据
│
└── KV Namespace (可选)
    └── schema-cache                 → Schema 缓存,减少 D1 查询延迟
```

**与 Express 版的对应关系**:

| Express (§4.1) | Cloudflare Workers | 说明 |
|:---|:---|:---|
| `express()` | `export default { fetch }` | Workers 原生 fetch 事件处理器 |
| `app.post('/cli/text_cli', handler)` | URL 路由匹配 | 手动路由或轻量路由库 |
| 内存中的路由表 | D1 `directives` 表 | 指令元数据持久化 |
| 环境变量 `SERVICE_TOKEN` | D1 `tokens` 表 + Workers Secrets | 多 Token + 配额管理 |
| `console.log` | D1 `usage_logs` 表 | 结构化日志,可查询 |
| Docker 部署 | `wrangler deploy` | 一条命令部署到全球边缘 |

### 11.2 项目结构

```text_cli/js/
├── src/
│   ├── index.js              # Worker 入口(fetch 事件处理器 + 路由)
│   ├── parser.js             # 指令解析器(正则匹配,与 Python 版逻辑一致)
│   ├── registry.js           # 指令注册表(启动时从代码注册)
│   ├── auth.js               # Token 鉴权(D1 可选)
│   ├── schema.js             # Schema 管理(D1 可选,回退静态文件)
│   └── handlers/
│       ├── index.js           # 自动聚合所有 handler
│       └── sample.js          # 示例指令 handler
├── schema/
│   └── text_cli_schema.json   # 静态 Schema 源文件
├── migrations/
│   └── 0001_init.sql          # D1 数据库迁移脚本(仅 D1 模式使用)
├── test/
│   ├── parser.test.js
│   ├── registry.test.js
│   └── integration.test.js
├── wrangler.toml              # Cloudflare Workers 配置
├── package.json
└── vitest.config.js
```

### 11.3 D1 数据库设计

**migrations/0001_init.sql**

```sql
-- 指令注册表:存储所有指令的元数据
CREATE TABLE IF NOT EXISTS directives (
  id TEXT PRIMARY KEY,
  domain TEXT NOT NULL,
  action TEXT NOT NULL,
  name TEXT NOT NULL,
  category TEXT,
  description TEXT,
  parameters_json TEXT DEFAULT '[]',
  prompt_template TEXT,
  trigger_keywords_json TEXT DEFAULT '[]',
  response_type TEXT DEFAULT 'text',
  response_example_json TEXT,
  handler_type TEXT DEFAULT 'static',
  enabled INTEGER DEFAULT 1,
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_directives_domain_action
  ON directives(domain, action);

-- Service Token 管理:支持多租户 + 配额
CREATE TABLE IF NOT EXISTS tokens (
  token_hash TEXT PRIMARY KEY,
  client_name TEXT NOT NULL,
  quota INTEGER DEFAULT -1,
  used INTEGER DEFAULT 0,
  enabled INTEGER DEFAULT 1,
  created_at TEXT DEFAULT (datetime('now'))
);

-- 调用日志:计费与审计
CREATE TABLE IF NOT EXISTS usage_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  request_id TEXT,
  directive_key TEXT NOT NULL,
  token_hash TEXT,
  params_json TEXT,
  result_status TEXT,
  response_time_ms INTEGER,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_usage_logs_created
  ON usage_logs(created_at);

CREATE INDEX IF NOT EXISTS idx_usage_logs_directive
  ON usage_logs(directive_key, created_at);
```

**初始化 D1 并导入 Schema**:

```bash
cd text_cli/js

# 创建 D1 数据库
wrangler d1 create text-cli-db
# 输出: ✅ Created database 'text-cli-db' with ID <uuid>
# 将 database_id 填入 wrangler.toml

# 执行迁移
wrangler d1 execute text-cli-db --file=migrations/0001_init.sql

# 导入静态 Schema 到 directives 表
node scripts/seed-directives.js
```

### 11.4 核心代码

#### 9.4.1 指令解析器 `src/parser.js`

与 Python 版逻辑完全一致,正则匹配 `指令:领域;动作,参数`:

```javascript
const DIRECTIVE_PATTERN = /^\s*指令[：:]([^;]+);([^,]+)(?:,(.+))?\s*$/;
const MAX_DIRECTIVE_LENGTH = 512;
const MAX_PARAMS = 20;

export class DirectiveParseError extends Error {
  constructor(message, code = 'INVALID_DIRECTIVE_FORMAT') {
    super(message);
    this.code = code;
  }
}

export function parseDirective(prompt) {
  if (!prompt || !prompt.trim()) {
    throw new DirectiveParseError('prompt is required');
  }

  prompt = prompt.trim();

  if (prompt.length > MAX_DIRECTIVE_LENGTH) {
    throw new DirectiveParseError(
      `directive exceeds max length (${MAX_DIRECTIVE_LENGTH})`
    );
  }

  const match = DIRECTIVE_PATTERN.exec(prompt);
  if (!match) {
    throw new DirectiveParseError(`invalid directive format: ${prompt}`);
  }

  const domain = match[1].trim();
  const action = match[2].trim();
  const rawParams = match[3];

  const params = [];
  if (rawParams) {
    for (const p of rawParams.split(',')) {
      const trimmed = p.trim();
      if (trimmed) params.push(trimmed);
    }
  }

  if (params.length > MAX_PARAMS) {
    throw new DirectiveParseError(
      `too many parameters (${params.length}), max ${MAX_PARAMS}`
    );
  }

  if (!domain) throw new DirectiveParseError('domain is empty');
  if (!action) throw new DirectiveParseError('action is empty');

  return {
    domain,
    action,
    params,
    raw: prompt,
    directiveKey: `指令:${domain};${action}`,
  };
}
```

#### 9.4.2 指令注册表 `src/registry.js`

代码中的 handler 通过 `registerHandler` 注册:

```javascript
const _registry = new Map();

export function registerHandler(domain, action, handler) {
  const key = `${domain};${action}`;
  _registry.set(key, handler);
}

export function dispatch(domain, action, params) {
  const key = `${domain};${action}`;
  const handler = _registry.get(key);
  if (!handler) {
    return `未找到匹配的指令: ${domain};${action}`;
  }
  return handler(params);
}

export function getRegisteredDirectives() {
  const result = {};
  for (const [key] of _registry) {
    const sepIdx = key.indexOf(';');
    const domain = key.slice(0, sepIdx);
    const action = key.slice(sepIdx + 1);
    if (!result[domain]) result[domain] = [];
    result[domain].push(action);
  }
  return result;
}

export function getRegistrySize() {
  return _registry.size;
}

export function clearRegistry() {
  _registry.clear();
}
```

#### 9.4.3 Token 鉴权 `src/auth.js`

支持两种模式:**D1 多 Token 模式**(有数据库时)和**单 Token 模式**(无数据库时回退到环境变量):

```javascript
const SERVICE_TOKEN = globalThis.SERVICE_TOKEN || '';

async function sha256Hex(text) {
  const data = new TextEncoder().encode(text);
  const hash = await crypto.subtle.digest('SHA-256', data);
  return [...new Uint8Array(hash)].map(b => b.toString(16).padStart(2, '0')).join('');
}

export async function verifyServiceToken(token, db) {
  if (!token) {
    return { allowed: false, clientName: '', message: 'Service-token 缺失' };
  }

  const clean = token.trim();

  if (db) {
    const hash = await sha256Hex(clean);
    const row = await db
      .prepare(
        'SELECT client_name, quota, used, enabled FROM tokens WHERE token_hash = ?'
      )
      .bind(hash)
      .first();

    if (!row) {
      return { allowed: false, clientName: '', message: 'Service-token 无效' };
    }
    if (!row.enabled) {
      return { allowed: false, clientName: row.client_name, message: 'Token 已禁用' };
    }
    if (row.quota >= 0 && row.used >= row.quota) {
      return {
        allowed: false,
        clientName: row.client_name,
        message: `配额已用尽 (${row.used}/${row.quota})`,
      };
    }
    return { allowed: true, clientName: row.client_name, message: '', tokenHash: hash };
  }

  if (!SERVICE_TOKEN) {
    return { allowed: true, clientName: 'anonymous', message: '' };
  }
  if (clean !== SERVICE_TOKEN) {
    return { allowed: false, clientName: '', message: 'Service-token 无效' };
  }
  return { allowed: true, clientName: 'authenticated', message: '' };
}

export async function incrementUsage(db, tokenHash) {
  if (!db || !tokenHash) return;
  await db
    .prepare('UPDATE tokens SET used = used + 1 WHERE token_hash = ?')
    .bind(tokenHash)
    .run();
}
```

#### 9.4.4 示例 Handler `src/handlers/sample.js`

```javascript
import { registerHandler } from '../registry.js';

registerHandler('示例领域', '回显', (params) => {
  return params.length > 0
    ? `回显结果: ${params.join(', ')}`
    : '回显结果: (无参数)';
});

registerHandler('示例领域', '问候', (params) => {
  const name = params[0] || '世界';
  return `你好, ${name}!`;
});

registerHandler('示例领域', '列表', () => {
  return '示例指令列表:\n- 回显: 回显参数\n- 问候: 问候指定名称\n- 列表: 显示此列表';
});
```

#### 9.4.5 Worker 入口 `src/index.js`

```javascript
import { parseDirective, DirectiveParseError } from './parser.js';
import { dispatch, getRegisteredDirectives } from './registry.js';
import { verifyServiceToken, incrementUsage } from './auth.js';
import { getSchema } from './schema.js';
import './handlers/index.js';

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function ok(text) {
  return json({ rst_types: 'text', rst_data: { text } });
}

function errorResponse(text, status = 400) {
  return json({ rst_types: 'text', rst_data: { text: `指令执行失败: ${text}` } }, status);
}

async function handleDirective(request, env) {
  const serviceToken = request.headers.get('Service-token');
  const auth = await verifyServiceToken(serviceToken, env.DB);

  if (!auth.allowed) {
    return json({ rst_types: 'text', rst_data: { text: `无权访问: ${auth.message}` } }, 403);
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return errorResponse('请求体不是有效 JSON');
  }

  const prompt = body?.prompt;
  if (!prompt) {
    return errorResponse('缺少 prompt 字段');
  }

  let parsed;
  try {
    parsed = parseDirective(prompt);
  } catch (e) {
    if (e instanceof DirectiveParseError) {
      return errorResponse(`${e.code}: ${e.message}`);
    }
    throw e;
  }

  const start = Date.now();
  const result = dispatch(parsed.domain, parsed.action, parsed.params);
  const elapsed = Date.now() - start;

  if (env.DB) {
    env.DB.prepare(
      `INSERT INTO usage_logs (directive_key, token_hash, params_json, result_status, response_time_ms)
       VALUES (?, ?, ?, ?, ?)`
    )
      .bind(parsed.directiveKey, auth.tokenHash || null, JSON.stringify(parsed.params), 'ok', elapsed)
      .run()
      .catch(() => {});
  }

  incrementUsage(env.DB, auth.tokenHash).catch(() => {});

  return ok(result);
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;

    if (request.method === 'POST' && path === '/cli/text_cli') {
      return handleDirective(request, env);
    }

    if (request.method === 'GET' && path === '/health') {
      return json({ status: 'ok', directives: getRegisteredDirectives() });
    }

    if (request.method === 'GET' && path === '/text_cli_schema.json') {
      const schema = await getSchema(env.DB);
      return json(schema);
    }

    return json({ error: 'Not Found' }, 404);
  },
};
```

### 11.5 Schema 管理

Schema 支持两种数据源:**D1 数据库**（启用时）和**静态 JSON 文件**（回退）。通过 `scripts/seed-directives.js` 将静态 Schema 导入 D1:

**`src/schema.js`**

```javascript
import staticSchema from '../schema/text_cli_schema.json';

export async function getSchema(db) {
  if (db) {
    const rows = await db
      .prepare(
        `SELECT id, name, category, description, domain, action,
                parameters_json, prompt_template, trigger_keywords_json,
                response_type, response_example_json
         FROM directives WHERE enabled = 1`
      )
      .all();

    const schema = {};
    for (const row of rows.results) {
      schema[row.id] = {
        id: row.id,
        name: row.name,
        category: row.category,
        description: row.description,
        directive: `指令:${row.domain};${row.action}`,
        parameters: JSON.parse(row.parameters_json || '[]'),
        prompt_template: row.prompt_template,
        trigger_keywords: JSON.parse(row.trigger_keywords_json || '[]'),
        response_type: row.response_type,
        response_example: row.response_example_json
          ? JSON.parse(row.response_example_json)
          : undefined,
      };
    }

    if (Object.keys(schema).length > 0) {
      return schema;
    }
  }

  return staticSchema;
}
```

### 11.6 wrangler.toml 配置

**完整模式(D1)**:

```toml
name = "text-cli-skill"
main = "src/index.js"
compatibility_date = "2026-05-01"
workers_dev = true

[[d1_databases]]
binding = "DB"
database_name = "text-cli-db"
database_id = "<your-database-id>"

[vars]
LOG_LEVEL = "info"
```

**精简模式(纯 Workers,无 D1)**:

```toml
name = "text-cli-skill"
main = "src/index.js"
compatibility_date = "2026-05-01"
workers_dev = true

[vars]
LOG_LEVEL = "info"
```

精简模式下:Token 回退到 `SERVICE_TOKEN` 环境变量,Schema 使用静态 JSON 文件,无调用日志。

### 11.7 添加新指令

**方式一:代码注册(推荐,适合有状态逻辑)**

在 `src/handlers/` 下新建文件,调用 `registerHandler`:

```javascript
// src/handlers/weather.js
import { registerHandler } from '../registry.js';

registerHandler('基础服务', '天气查询', (params) => {
  const city = params[1] || '威海';
  return `${city}明天天气: 23°C, 多云`;
});
```

然后在 `src/handlers/index.js` 中导入:

```javascript
import './sample.js';
import './weather.js';
```

**方式二:D1 动态注册(适合简单模板)**

通过管理接口将指令元数据写入 D1,handler 使用内置模板引擎:

```bash
wrangler d1 execute text-cli-db --command=\
  "INSERT INTO directives (id, domain, action, name, handler_type)
   VALUES ('weather_query', '基础服务', '天气查询', '天气查询', 'template')"
```

### 11.8 部署流程

```bash
cd text_cli/js

# 1. 安装依赖
npm install

# 2. 本地开发(模拟 D1)
wrangler dev

# 3. 创建 D1 数据库(首次)
wrangler d1 create text-cli-db

# 4. 执行数据库迁移
wrangler d1 execute text-cli-db --file=migrations/0001_init.sql

# 5. 导入指令 Schema
node scripts/seed-directives.js

# 6. 添加 Service Token
wrangler d1 execute text-cli-db --command=\
  "INSERT INTO tokens (token_hash, client_name, quota)
   VALUES ('<sha256-hash>', '测试客户端', 1000)"

# 7. 部署到 Cloudflare
wrangler deploy
```

部署完成后:

```bash
# 健康检查
curl https://text-cli-skill.<subdomain>.workers.dev/health

# 执行指令
curl -X POST https://text-cli-skill.<subdomain>.workers.dev/cli/text_cli \
  -H "Content-Type: application/json" \
  -H "Service-token: your-token" \
  -d '{"prompt":"AI:示例领域;回显,hello"}'

# 获取 Schema
curl https://text-cli-skill.<subdomain>.workers.dev/text_cli_schema.json
```

### 11.9 三种路径对比

| | Express (§4.1) | FastAPI (§4.2) | **Workers (§11)** |
|:---|:---|:---|:---|
| **运行时** | Node.js | Python | Cloudflare Workers (V8) |
| **数据库** | 无(内存) | 无(内存) | **D1 (可选,不配则回退静态文件)** |
| **部署** | Docker / VM | Docker / VM | **`wrangler deploy`** |
| **冷启动** | 秒级 | 秒级 | **< 5ms** |
| **全球分发** | 需自建 CDN | 需自建 CDN | **内置 300+ 节点** |
| **Token 管理** | 单 Token(环境变量) | 单 Token(环境变量) | **单 Token 或 D1 多 Token + 配额** |
| **调用日志** | 无 | 无 | **D1 结构化日志(需 D1)** |
| **Schema 热更新** | 需重启 | 需重启 | **D1 写入即生效(需 D1)** |
| **费用** | 服务器费用 | 服务器费用 | **免费额度:10万次/天** |
| **适用场景** | 本地开发 / 自建服务 | 本地开发 / 自建服务 | **全球边缘部署** |

---
