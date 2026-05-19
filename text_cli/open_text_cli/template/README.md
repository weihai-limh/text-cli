# template

Prompt template library with placeholder substitution.

## Install

```
AI:text-cli;install,template
```

## Dependencies

**Data file** (distributed with package):
- `prompt_templates.json` — template definitions (id, text, description)

**Runtime dependency**: `handlers.image` (for output caching).

## Directives

| Directive | Description |
|-----------|-------------|
| `template;list` | List all available templates |
| `template;use,<id>[,key=val,...]` | Render template with substitution, output to cache |

## Example

```
AI:template;list
→ 默认: 通用场景分析
   风景: 侧重自然景观
   城市: 侧重城市环境

AI:template;use,默认,地点=威海,时间=清晨,设备=手机
→ cache:a1b2c3d4e5f6
  请描述这张手机于清晨在威海拍摄的照片。描述场景、主体、光线、色彩和地貌特征。
```

## Architecture

```
Python package with data file
  ├── handler.py              — @directive registration + template rendering
  ├── prompt_templates.json   — template definitions (distributed with package)
  └── schema.json             — directive declarations
```
