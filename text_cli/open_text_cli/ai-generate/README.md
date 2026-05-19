# ai-generate

Image and video generation via configurable AI provider. Models are in configuration, never in code.

## Install

```
AI:text-cli;install,ai-generate
```

## Dependencies

- `ai-inference` package (shared API key resolution)
- `config/model_aliases.json` — provider and model definitions

## Directives

| Directive | Description |
|-----------|-------------|
| `image-gen;generate,<prompt>[,<size>]` | Generate image from text prompt |
| `video;generate,<prompt>[,<size>[,<quality>]]` | Submit async video task |
| `video;status,<task_id>` | Poll video task status |

## Example

```
AI:image-gen;generate,A cat sitting on a cloud
→ Generation succeeded
   URL: https://...

AI:video;generate,A drone flying over mountains,1920x1080
→ Video task submitted
   task_id: abc123-def456

AI:video;status,abc123-def456
→ status: SUCCESS
   video_url: https://...
```

## Architecture

```
Python package (depends on ai-inference for key resolution)
  ├── handler.py    — @directive registration + HTTP API calls
  └── schema.json   — 3 directives
```
