# text-cli v{VERSION} 隐私与安全声明

## 数据流向

```
用户/AI → curl/HTTP POST → service(:28050) → 本地 handler 或 proxy → copilot(:20260) → 本机操作
```

容器形态的数据流向不变，但宿主机侧多一层外挂卷（见「容器形态的安全边界」）：

```
用户/AI → HTTP POST → service(:28050, 容器) → handler/proxy → copilot(:20260, 127.0.0.1) → 本机操作
                                  ↘ 外挂卷 /app/data(sqllite) /app/runtime(代码) /packages(包源)
```

| 层级 | 出网 | 存盘 |
|------|:---:|:---:|
| copilot | 否（仅 127.0.0.1） | 否 |
| service handler | 取决于指令包（如天气 API 出网） | 否（无默认存储） |
| A6 SQL | 否 | 是（SQLite，配额/任务数据） |

## 安全边界（本机 / 局域网）

- **copilot 仅绑 127.0.0.1**——外部网络无法直接访问本机文件/Git/终端
- **service 绑 0.0.0.0**——局域网可达，生产环境建议前端放置反向代理 + Token 鉴权
- **无默认遥测**——不收集使用数据或崩溃报告
- **无默认持久化用户数据**——未启用 A6 SQL 时不写磁盘

## 安全边界（容器 / Docker 形态）

容器为薄沙箱镜像：只含 Python 环境 + 代码种子(seed)，代码/包/数据外挂宿主机。相应安全考量：

- **copilot 红线在容器内同样适用**：copilot(:20260) 仅本机回环可达。
  - 单 copilot 用 `--network=host` 经回环访问；**禁 `-p 20260:20260` 暴露到 0.0.0.0**
  - 融合镜像（service）里 copilot 绑 127.0.0.1，不对外映射
- **外挂卷数据归属宿主文件系统**：`runtime/`、`data/`、`packages/` 挂到宿主机路径，是宿主机文件的一部分。
  - 数据默认无镜像级加密，**宿主机文件权限即安全边界**
  - `/app/data`（sqlite：配额/任务数据）持久化在宿主卷，重建不丢
- **镜像内代码/包（seed + 三类文件）随镜像分发**：docs/手册、packages（标准指令包）、protocol(SDK) 随镜像 bake。
  - packages 含标准指令包，同第三方依赖考量——出站请求由指令包 handler 发起（见下节）
- **容器进程以非 root 运行**（UID 1001）：降低容器逃逸/提权面。
- **热更新边界**：代码外挂在宿主机 `runtime/`，改动的是宿主机文件——宿主自身安全即容器安全前提。

## Token 鉴权

- service→copilot 内部使用 Bearer Token（`auxiliary_config.json` 中配置）
- 公网暴露时，service 前端应加 Token 鉴权（A5 endpoint 提供完整实现）
- 容器形态：`SERVICE_TOKEN` 环境变量注入；生产务必设置（默认空 = 匿名开放）

## 第三方依赖

所有出站请求均由对应指令包的 handler 发起——text-cli 框架本身不主动出站。
出站目标和传输方式完全取决于已安装的指令包——查看每个包的 schema.json
了解其外部依赖详情。容器 bake 的 standard-python 标准包同样遵循此原则。

---

*text-cli v{VERSION} 隐私与安全声明 · 补容器(Docker)形态安全边界（2026-08-14）*
