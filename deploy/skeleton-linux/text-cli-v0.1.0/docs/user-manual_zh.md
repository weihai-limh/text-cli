# text-cli v0.1.0 使用手册

## 服务组成

| 进程 | 端口 | 绑定 | 职责 |
|------|:---:|------|------|
| copilot | 20260 | 127.0.0.1 | 本机文件/Git/shell/终端操作 |
| service | 28050 | 0.0.0.0 | 指令调度、路径编排、MCP 桥、聚合降级 |

**copilot 仅本机可达——这是安全边界，不是配置差异。**

## 配置

### copilot 配置

`copilot/auxiliary_config.json`——首次启动自动从 `.example.json` 初始化。

### service 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `TEXT_CLI_HOME` | 启动目录 | 项目根目录 |
| `PORT` | 28050 | service 监听端口 |

## 常用指令格式

```
AI:<领域>;<动作>,<参数1>,<参数2>,...
```

示例：
- `AI:基础应用;天气查询,北京` — 天气查询
- `AI:文件;读取,/path/to/file` — 读取本机文件（通过 copilot）
- `AI:AI;推理,今天天气怎么样` — LLM 推理

## 装指令包

```bash
# 安装
curl -X POST http://localhost:28050/text-cli/cli ^
  -H "Content-Type: application/json" ^
  -d "{\"directive\": \"AI:text-cli;install,包名\"}"

# 查看已安装
curl http://localhost:28050/text-cli/query
```

## 路径编排

多条指令串联成链——路径只做编排和插值，文件 IO/API 调用/推理全部通过指令。

## 聚合降级

同类能力有多个提供方时自动切换。调用方不感知——`AI:地图;geocode,...` 在 tx-map 耗尽时自动切 gd-map。

## 常见问题

**Q: 启动后 curl 无响应？**
A: 等待 `start.bat` 输出"[OK]"确认。

**Q: 端口被占用？**
A: 设置 `PORT=28051` 环境变量后重新启动。

**Q: copilot 不响应？**
A: copilot 仅绑 127.0.0.1——从本机 curl 可以，从局域网其他机器不行（这是设计行为）。
