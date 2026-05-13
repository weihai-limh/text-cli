# open_text_cli — 开源文本指令包

text-cli 项目的可复用指令实现。每个子目录是一个独立可引入的能力包。

## 使用方式

从本目录按需取用所需的指令包，放入你的 A3 服务 handlers/ 目录下。
每个包声明其依赖（密钥、外部 API），不绑定特定实现。

## 包清单

| 包 | 指令 | 依赖 | 密钥需求 |
|----|------|------|----------|
| `ai_inference/` | AI;推理 / AI;视觉 | 多 provider API | `api_key`（zhipu/xunfei/modelscope） |
| `ai_generate/` | AI;图像 / AI;视频 | CogView/CogVideoX API | `api_key`（智谱） |
| `embed/` | 嵌入;文本 | bge-m3 API | `api_key`（ModelScope/智谱） |

## 密钥注入

所有包通过环境变量读取密钥，不硬编码、不绑定 SQLite：

```
ZHIPU_KEY=xxx        # 智谱 API 密钥
XUNFEI_KEY=xxx       # 讯飞 API 密钥
MODELSCOPE_KEY=xxx   # ModelScope API 密钥
```

升级到 A6（SQLite 密钥管理）后，可切换为 key_registry 动态读取。

## 渐进式兼容

- **A3 用户**：直接复制 handler.py 到 handlers/，设环境变量，即可运行
- **A6 用户**：升级后密钥可从 SQLite key_registry 读取，不改变 handler 逻辑
- **A7 用户**：MCP 路由可与本地指令共存，互不冲突
