# AI Inference

**Directives:** `AI辅助;推理`, `AI辅助;视觉`
**Dependencies:** `text_cli_modules/ai/`
**Configuration:** `model_aliases.example.json` → `model_aliases.json`

AI text reasoning and vision-language (VL) analysis. Handles model routing, fallback chains, and time-aware provider selection. All model/provider names are in configuration, never in code.

## Install

```bash
cp examples/text-cli/ai_inference/handler.py server/python/handlers/ai_inference.py
cp examples/text-cli/ai_inference/model_aliases.example.json server/python/config/model_aliases.example.json
cp server/python/config/model_aliases.example.json server/python/config/model_aliases.json
# Edit model_aliases.json — fill in your provider names, URLs, and model lists
```

## Usage

```
AI:ai_inference;reason,What is the capital of France?,auto
AI:ai_inference;vision,Describe this image,[image_url],auto
```

Modes: `auto` (time-aware), `fast` (free tier chain), `quality` (paid chain), or a specific model name.

---

# AI 推理

**指令:** `AI辅助;推理`, `AI辅助;视觉`
**依赖:** `text_cli_modules/ai/`
**配置:** `model_aliases.example.json` → `model_aliases.json`

提供 AI 文本推理和视觉-语言（VL）分析能力。内置模型路由、回退链和时段感知选择。所有模型名和供应商信息在配置文件中，不硬编码在代码中。

## 安装

```bash
cp examples/text-cli/ai_inference/handler.py server/python/handlers/ai_inference.py
cp examples/text-cli/ai_inference/model_aliases.example.json server/python/config/model_aliases.example.json
cp server/python/config/model_aliases.example.json server/python/config/model_aliases.json
# 编辑 model_aliases.json — 填入供应商名称、API 地址和模型列表
```

## 使用

```
指令:AI辅助;推理,法国的首都是哪里？,auto
指令:AI辅助;视觉,描述这张图片,[图片地址],auto
```

模式: `auto`（时段感知）、`fast`（免费模型链）、`quality`（付费链），或直接指定模型名。
