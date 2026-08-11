# text-cli v0.1.1 — 分发包

## 你拿到了什么

不同分发包包含不同层级的运行时。打开你的分发包，看根目录有什么文件夹：

| 你的文件夹 | 对应层级 | 可用能力 |
|-----------|:------:|---------|
| `copilot/` | A2 | 本机文件/Git/shell 代理 |
| 以上 + `service/` | A3+ | 以上 + 指令调度 + 包管理 |
| 以上 + `service/aggregate/` | A8+ | 以上 + 聚合降级 |
| 以上 + `service/pro_registry.json` | A9 | 全量——路径编排 + MCP + 门面 |

> 如果根目录有 `start-endpoint.bat`（或 `start-endpoint.sh`）而非 `start.bat`，这是 **endpoint 网关包**——独立鉴权转发服务，端口 29050。

## 三步上手

### 1. 启动

运行启动脚本。脚本自动适配层级——A2 仅启动 copilot(:20260)，A3+ 额外启动 service(:28050)。

```
Windows: 双击 start.bat
Linux:   chmod +x start.sh && ./start.sh
```

Endpoint 网关包：
```
Windows: 双击 start-endpoint.bat
Linux:   chmod +x start-endpoint.sh && ./start-endpoint.sh
```

### 2. 验证

A2 分发包：
```bash
curl http://127.0.0.1:20260/text-cli/health
```

A3+ 分发包：
```bash
curl http://localhost:28050/text-cli/health
```

Endpoint 网关包：
```bash
curl http://localhost:29050/health
```

### 3. 查看可用指令（A3+）

```bash
curl -X POST http://localhost:28050/text-cli/cli -H "Content-Type: application/json" -d '{"prompt":"AI:text-cli;query"}'
```

A2 分发包需先安装指令包后再查询：
```bash
curl -X POST http://127.0.0.1:20260/text-cli/cli -H "Content-Type: application/json" -d '{"prompt":"AI:text-cli;co-list"}'
```

---

## 分发包信息

| 项 | 值 |
|----|-----|
| 版本 | v0.1.1 |
| 协议 | SPEC v1.3.2 |
| copilot | 端口 20260（仅 127.0.0.1） |
| service | 端口 28050（0.0.0.0） |
| endpoint | 端口 29050（0.0.0.0） |

## 配套文档

- `user-manual_zh.md` — 完整使用手册与配置参考
- `deploy-checklist_zh.md` — 上线前核对清单
- `privacy-checklist_zh.md` — 数据流向与安全声明
