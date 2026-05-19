# ai-inference

AI text reasoning and vision-language analysis via configurable AI provider.
All provider names and models are in configuration, never in code.
Supports multi-mode model selection, fallback chains, and time-aware provider routing.

## Install

```
AI:text-cli;install,ai-inference
```

## Dependencies

**Runtime modules** (must be deployed to the service):
- `text_cli_modules/ai/` — inference engine (`text_inference`, `vision_inference`, `get_period`)
- `text_cli_modules/key/` — key registry reader

**Configuration**:
- `config/model_aliases.json` — model provider definitions and fallback chains

**Credentials**:
- AI provider API key registered in key_registry: `AI:key;register,ai_api_key,<key>,api_key`

## Directives

| Directive | Description |
|-----------|-------------|
| `AI;reasoning,<prompt>[,<mode>]` | Text inference with multi-mode model selection |
| `AI;vision,<prompt>,<image>[,<mode>]` | Vision-language inference (URL, base64, or cache reference) |

**Modes**: `auto` (time-aware), `fast` (free models), `quality` (paid models), or a specific model name.
Time routing: 0-6h uses paid models, 6-24h uses free models.

## Example

```
AI:key;register,ai_api_key,<your-key>,api_key
AI:AI;reasoning,What is the capital of France?,auto
→ Paris is the capital of France.

AI:AI;vision,Describe this image,https://example.com/photo.jpg,quality
→ The image shows a sunset over a mountain range...
```

## Architecture

```
A3 Service extension
  ├── handler.py          — @directive registration + model routing
  ├── schema.json         — directive declarations
  ├── text_cli_modules/ai/ — inference engine (runtime dependency)
  └── config/model_aliases.json — provider configuration
```

Key retrieval uses three-tier fallback: SQLite key_registry → copilot encrypted JSON → environment variables.
