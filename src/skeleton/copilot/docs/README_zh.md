# copilot 分组

## 定位

copilot 分组下的骨架层绑定 **copilot 运行时（127.0.0.1:20260）**——它是部署在终端本地的 AI 调度服务。

text-cli 协议在 Agent 同机的本地实现。骨架提供 dispatch 引擎 + 编解码 + 密钥路由 + Skill 桥。具体能力（文件、Git、邮件等）由指令包安装时注入。

```
Agent                   copilot                  远程端点
  │                       │                        │
  ├─ AI:codec;encode ───→ │ ─→ 本地编解码          │
  ├─ AI:key;get ────────→ │ ─→ 密钥路由            │
  └─ AI:file;read ──────→ │ ─→ [files 包] 文件系统 │
```

Agent 全程不需要持有密码或 API Key——凭据由 copilot 居中持有，通过环境变量注入。

## 层级

| 层 | 名称 | 核心能力 |
|:---:|------|------|
| A2 | copilot | 本地 Copilot——cmd engine、Skill Bridge、三层 dispatch 匹配、输出适配 |

### A2 核心文件

| 文件 | 作用 |
|------|------|
| `text-cli-copilot.py` | HTTP 服务入口（端口 20260） |
| `core.py` | dispatch 引擎核心 |
| `whitelist_loader.py` | CLI 白名单加载 |
| `auxiliary_config.json` | 辅助配置 |
| `handlers/` | 骨架 handler（adapters/codec/key/package_manager/skill_bridge） |
| `config/` | 运行配置：key_routing.json、skill_bridge_routes.json 等 |
| `packages/` | 指令包安装目标（空目录） |

### 骨架 Handler

| 文件 | 指令 | 说明 |
|------|------|------|
| `codec.py` | `encode;base64` `encode;hex` | Base64/Hex 编解码 |
| `key.py` | `key;register` `key;revoke` `key;list` | 密钥路由（按配置分发，不存储） |
| `adapters.py` | — | 通用响应适配器协议 |
| `skill_bridge.py` | — | 通用桥——一个 handler，N 个 skill 共享 |
| `package_manager.py` | — | 包自管理（co-install/co-uninstall/co-list） |

### 包 Handler（运行时安装）

以下能力由指令包提供，通过 `AI:text-cli;co-install,<包名>` 安装到 `packages/` 目录：

| 包 | 指令 |
|------|------|
| files | 文件;读写/列表/移动 |
| git | Git;状态/推送 |
| mail | 邮件;发送 |
| system | 系统;健康/状态 |
| media | 媒体;加载/下载 |
| terminal | 终端;命令 |

## 启动与验证

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `TEXT_CLI_HOME` | `~/text-cli` | 项目根目录 |

### 启动

```bash
cd deploy/A2-copilot/copilot
python3 text-cli-copilot.py
```

### 验证

```bash
curl http://localhost:20260/text-cli/health
# {"status": "ok"}

curl -X POST http://localhost:20260/text-cli/cli \
  -H 'Authorization: Bearer <token>' \
  -d '{"prompt":"AI:encode;base64,hello"}'
```

## 安全边界

copilot 锁在 **127.0.0.1**——仅本机可访问。可以暴露终端操作能力（cmd handler），这是 service（0.0.0.0）不能做的。

凭据通过**环境变量注入**，不写入配置文件。`${VAR_NAME}` 占位符在服务启动时一次性解析。

## 历史文档

`text-cli-copilot_programme_CN.md`（已归档至 `.dev/docs/old_docs/`） — 技术方案 v2.0，2026-05-10。标注为历史参考，部分细节可能与当前实现不一致。

## 构建

参与 `build-all.py` 的标准累积链。

---

_2026-07-16_
