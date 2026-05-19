# ai-generate · ai生成

图像与视频生成，基于可配置的 AI 供应商。模型在配置文件中定义。

## 安装

```
AI:text-cli;install,ai-generate
```

## 依赖

- `ai-inference` 包（共享 API 密钥解析）
- `config/model_aliases.json` — 供应商和模型定义

## 指令

| 指令 | 说明 |
|------|------|
| `image-gen;generate,<提示词>[,<尺寸>]` | 文本提示词生成图像 |
| `video;generate,<提示词>[,<尺寸>[,<质量>]]` | 提交异步视频任务 |
| `video;status,<任务ID>` | 轮询视频任务状态 |

中文别名：`图像;生成` `视频;生成` `视频;状态`

## 示例

```
AI:图像;生成,一只坐在云上的猫
→ Generation succeeded
   URL: https://...

AI:视频;生成,无人机飞越山脉,1920x1080
→ Video task submitted
   task_id: abc123-def456

AI:视频;状态,abc123-def456
→ status: SUCCESS
   video_url: https://...
```

## 架构

```
Python 包（依赖 ai-inference 解析密钥）
  ├── handler.py    — @directive 注册 + HTTP API 调用
  └── schema.json   — 3 条指令
```
