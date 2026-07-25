# ai-inference · AI 推理

基于可配置 AI 供应商的文本推理与视觉分析。
所有供应商名和模型在配置文件中，不硬编码在代码中。
支持多模式模型选择、回退链和时段感知路由。

## 安装

```
AI:text-cli;install,ai-inference
```

## 依赖

**运行时模块**（需部署到服务）：
- `text_cli_modules/ai/` — 推理引擎（`text_inference`、`vision_inference`、`get_period`）
- `text_cli_modules/key/` — 密钥注册表读取

**配置文件**：
- `config/model_aliases.json` — 模型供应商定义与回退链配置

**凭据**：
- AI 供应商 API 密钥需注册到 key_registry：`AI:key;注册,ai_api_key,<key值>,api_key`

## 指令

| 指令 | 说明 |
|------|------|
| `ai;infer,<提示词>[,<模式>]` | 文本推理，支持多模式模型选择 |
| `ai;vision,<提示词>,<图片>[,<模式>]` | 视觉推理（URL、base64 或缓存引用） |

**模式**：`auto`（时段感知）/ `fast`（免费模型）/ `quality`（付费模型）/ 直接指定模型名。
时段路由：0-6 时使用付费模型，6-24 时使用免费模型。

## 示例

```
AI:key;注册,ai_api_key,<你的密钥>,api_key
AI:ai;infer,法国的首都是哪里？,auto
→ 法国的首都是巴黎。

AI:ai;vision,描述这张图片,https://example.com/photo.jpg,quality
→ 图片显示山脉上方的日落...
```

## 架构

```
A3 Service 扩展
  ├── handler.py           — @directive 注册 + 模型路由
  ├── schema.json          — 指令声明
  ├── text_cli_modules/ai/ — 推理引擎（运行时依赖）
  └── config/model_aliases.json — 供应商配置
```

密钥读取采用三级回退：SQLite key_registry → copilot 加密 JSON → 环境变量。
