# text_cli/python — 技能服务模板

可被 `server/` 集成端点直接调用的标准指令服务。开发者以此模板为骨架，用 `@directive` 装饰器注册自己的指令处理函数。

---

## 目录结构

```
text_cli/python/
├── main.py                          # FastAPI 入口（lifespan + 指令分发）
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .gitignore
├── config/
│   └── text_cli_schema.json         # 指令 Schema（元数据与 URL）
├── core/
│   ├── __init__.py
│   ├── parser.py                    # 指令文本解析（正则 → ParsedDirective）
│   ├── auth.py                      # Service Token 鉴权
│   ├── registry.py                  # @directive 装饰器注册表 + dispatch 分发
│   └── response.py                  # ok() / error() 标准响应
└── handlers/
    ├── __init__.py                  # 自动发现并导入所有 handler 模块
    └── sample.py                    # 示例指令（回显 / 问候 / 列表）
```

---

## 核心模块职责

| 模块 | 职责 |
|:---|:---|
| `core/parser.py` | 将 `指令:领域;动作,参数...` 解析为 `ParsedDirective`，含格式校验和长度/参数上限 |
| `core/registry.py` | `@directive(domain, action)` 装饰器注册 + `dispatch()` 路由分发 |
| `core/auth.py` | 从环境变量 `SERVICE_TOKEN` 校验请求头 `Service-token` |
| `core/response.py` | `ok(text)` / `error(text)` 统一响应格式 |
| `handlers/` | 新增指令只需在此目录加 `.py` 文件并用 `@directive` 装饰——`__init__.py` 自动发现 |

---

## 快速启动

```bash
cd text_cli/python
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

启动后访问：
- `GET /health` — 查看已注册指令
- `GET /text_cli_schema.json` — 查看 Schema
- `POST /cli/text_cli` — 发送文本指令

## 注册新指令

```python
# handlers/my_handler.py
from core.registry import directive

@directive("基础应用", "天气查询")
def weather(params: list[str]) -> str:
    city = params[0] if params else "默认城市"
    return f"{city}天气: 晴, 22°C"
```

无需修改任何其他文件——`handlers/__init__.py` 启动时自动导入。

### 鉴权

设置环境变量 `SERVICE_TOKEN` 开启鉴权，调用方需携带：

```
Service-token: your-service-token
```

### Docker

```bash
docker compose up --build -d
```
