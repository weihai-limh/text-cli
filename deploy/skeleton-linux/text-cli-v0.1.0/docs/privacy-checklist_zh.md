# text-cli v0.1.0 隐私与安全声明

## 数据流向

```
用户/AI → curl/HTTP POST → service(:28050) → 本地 handler 或 proxy → copilot(:20260) → 本机操作
```

| 层级 | 出网 | 存盘 |
|------|:---:|:---:|
| copilot | 否（仅 127.0.0.1） | 否 |
| service handler | 取决于指令包（如天气 API 出网） | 否（无默认存储） |
| A6 SQL | 否 | 是（SQLite，配额/任务数据） |

## 安全边界

- **copilot 仅绑 127.0.0.1**——外部网络无法直接访问本机文件/Git/终端
- **service 绑 0.0.0.0**——局域网可达，生产环境建议前端放置反向代理 + Token 鉴权
- **无默认遥测**——不收集使用数据或崩溃报告
- **无默认持久化用户数据**——未启用 A6 SQL 时不写磁盘

## Token 鉴权

- service→copilot 内部使用 Bearer Token（`auxiliary_config.json` 中配置）
- 公网暴露时，service 前端应加 Token 鉴权（A5 endpoint 提供完整实现）

## 第三方依赖

| 指令包 | 数据出站目标 | 传输 |
|------|------|:---:|
| tx-map / bd-map / gd-map | 腾讯/百度/高德地图 API | HTTPS |
| zhipu-aiability | 智谱 AI API | HTTPS |
| MCP 桥接 | 对应 MCP server 地址 | HTTP/HTTPS |

**所有出站请求均由对应指令包的 handler 发起——text-cli 框架本身不主动出站。**
