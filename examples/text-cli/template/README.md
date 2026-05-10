# Prompt Templates

**Directives:** `模板;列表`, `模板;使用`
**Dependencies:** None
**Configuration:** `prompt_templates.json` (no secrets, can be shared)

Deterministic prompt template system for EXIF-to-text conversion and photo analysis. Zero AI tokens for prompt generation — template substitution only. Prevents hallucination by transcribing known facts without inference.

## Install

```bash
cp examples/text-cli/template/handler.py server/python/handlers/template.py
cp examples/text-cli/template/prompt_templates.json server/python/config/prompt_templates.json
```

## Usage

```
AI:template;list
AI:template;use,photo_describe,{"地点":"Weihai","时间":"2026-05-10 14:30:00"}
```

---

# 提示模板

**指令:** `模板;列表`, `模板;使用`
**依赖:** 无
**配置:** `prompt_templates.json`（不含密钥，可共享）

确定性提示模板系统，用于 EXIF 到文本的转换和照片分析。零 AI token 消耗——纯模板替换。通过转录已知事实而非推理，防止幻觉。

## 安装

```bash
cp examples/text-cli/template/handler.py server/python/handlers/template.py
cp examples/text-cli/template/prompt_templates.json server/python/config/prompt_templates.json
```

## 使用

```
指令:模板;列表
指令:模板;使用,photo_describe,{"地点":"威海","时间":"2026-05-10 14:30:00"}
```
