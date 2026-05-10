# AI Generation

**Directives:** `image;generate` (alias: `图像;生成`), `video;generate` (alias: `视频;生成`), `video;status` (alias: `视频;状态`)
**Dependencies:** `text_cli_modules/key/`
**Configuration:** `model_aliases.example.json` → `model_aliases.json`

Image and video generation via external AI APIs. API endpoints and model names are loaded from config, never hardcoded.

## Install

```bash
cp examples/text-cli/ai_generate/handler.py server/python/handlers/ai_generate.py
cp examples/text-cli/ai_generate/model_aliases.example.json server/python/config/model_aliases.example.json
```

## Usage

```
AI:image;generate,A whale jumping through ocean waves,1024x1024
AI:video;generate,Slow motion waves crashing on rocks,1024x576,standard
AI:video;status,<task_id>
```

---

# AI 生成

**指令:** `image;generate` (别名: `图像;生成`), `video;generate` (别名: `视频;生成`), `video;status` (别名: `视频;状态`)
**依赖:** `text_cli_modules/key/`
**配置:** `model_aliases.example.json` → `model_aliases.json`

通过外部 AI API 生成图像和视频。API 端点和模型名从配置文件读取，不硬编码。

## 安装

```bash
cp examples/text-cli/ai_generate/handler.py server/python/handlers/ai_generate.py
cp examples/text-cli/ai_generate/model_aliases.example.json server/python/config/model_aliases.example.json
```

## 使用

```
AI:image;generate,一只在海浪中跳跃的鲸鱼,1024x1024
AI:video;generate,海浪拍打礁石的慢镜头,1024x576,standard
AI:video;status,<task_id>
```
