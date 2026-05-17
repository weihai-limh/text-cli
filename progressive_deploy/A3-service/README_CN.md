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

## 核心模块职责

| 模块 | 职责 |
|:---|:---|
| `core/parser.py` | 将 `指令:领域;动作,参数...` 解析为 `ParsedDirective`，含格式校验和长度/参数上限 |
| `core/registry.py` | `@directive(domain, action)` 装饰器注册 + `dispatch()` 路由分发 |
| `core/auth.py` | 从环境变量 `SERVICE_TOKEN` 校验请求头 `Service-token` |
| `core/response.py` | `ok(text)` / `error(text)` 统一响应格式 |
| `handlers/` | 新增指令只需在此目录加 `.py` 文件并用 `@directive` 装饰——`__init__.py` 自动发现 |

## 快速启动

```bash
cd text_cli/python
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

### 注册新指令

```python
# handlers/my_handler.py
from core.registry import directive

@directive("基础应用", "天气查询")
def weather(params: list[str]) -> str:
    city = params[0] if params else "默认城市"
    return f"{city}天气: 晴, 22°C"
```

无需修改任何其他文件——`handlers/__init__.py` 启动时自动导入。

### Docker

```bash
docker compose up --build -d
```

---

## handler_inits 自动加载

不再为每个包在 main.py 里写 try/except 块。所有 handler 的初始化收束到 `config/handler_inits.py` 清单：

```python
HANDLER_INITS = [
    ("handlers.key", "init_key_handler", "db", None),
    ("handlers.quota_handler", "init_quota_handler", "quota", None),
    ...
]
```

`text-cli;install` 安装包后自动追加条目，`text-cli;uninstall` 卸载时自动移除。重启服务后新包自动加载——加包不再改 main.py。

## manifest 包生命周期

每个已安装的包在 `config/installed_packages.json` 中有记录：

```json
{
  "tx-cloud": {
    "id": "tx-cloud", "domain": "tx-cloud", "type": "native",
    "source": "/root/text-cli-package/tx-cloud/",
    "files": {"handler": "handlers/tx_cloud_handler.py"},
    "directives": ["tx-cloud;translation", "tx-cloud;asr", ...],
    "installed_at": "2026-05-17T10:28:00"
  }
}
```

manifest 支撑三个操作：
- **export**：读 manifest → 按 type 重组文件 → 输出到 `text-cli-package/<id>/`
- **packages**：列出已安装包及指令清单
- **uninstall**：删文件 + 清理 manifest 条目

## nocode 指令包

非代码经验成为一等指令包类型。花店老板的六篇 Markdown + 一份症状索引 + 一条路径声明——不需要 handler.py。平台通过 `tc-markdown;read` 读取经验文件，AI 推理做诊断。

## 指令包导出

```
text-cli;export,<id>      → 单包导出到 text-cli-package/
text-cli;export-all       → 全量导出
text-cli;packages         → 列出已安装包
```

导出的包结构与安装格式一致，可被 `text-cli;install` 直接消费。
