# text-cli v{VERSION} — Windows 本地部署包

## 这是什么

text-cli 是一个文本指令调度平台。"AI:领域;动作,参数" 格式的指令，驱动本机文件/Git/终端操作 + 远程 API 调用 + MCP 生态工具。

本包包含 **A2 copilot**（本机操作代理）和 **A9 service**（全量累积平台——路径编排、SQL 持久层、MCP 桥、聚合降级）。

## 三步上手

### 1. 启动

双击 `start.bat` —— 脚本自动安装依赖、初始化配置、启动 copilot（127.0.0.1:20260）和 service（0.0.0.0:28050）。

### 2. 测试

```bash
curl -X POST http://localhost:28050/text-cli/cli ^
  -H "Content-Type: application/json" ^
  -d "{\"directive\": \"AI:基础应用;天气查询,北京\"}"
```

### 3. 查看可用指令

```bash
curl http://localhost:28050/text-cli/schema
```

---

## 版本

| 项 | 值 |
|----|-----|
| 版本 | v{VERSION} |
| 协议 | SPEC v1.3.1 |
| copilot | 端口 20260（仅 127.0.0.1） |
| service | 端口 28050（0.0.0.0） |

**更多信息**：
- `user-manual_zh.md` — 完整配置与使用手册
- `deploy-checklist_zh.md` — 上线前核对清单
- `privacy-checklist_zh.md` — 数据流向与安全声明
