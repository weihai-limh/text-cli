# embed

Text embedding, similarity comparison, and semantic matching via configurable embedding provider.

## Install

```
AI:text-cli;install,embed
```

## Dependencies

**Runtime modules** (must be deployed to the service):
- `text_cli_modules/embed/` — embedding engine

**Credentials**:
- Embedding provider API key: `AI:key;register,embedding_api_key,<key>,api_key`

## Directives

| Directive | Description |
|-----------|-------------|
| `semantic;encode,<text>[,<mode>]` | Encode text to vector. Modes: A=256, B=512 (default), C=1024, D=2048 |
| `semantic;similarity,<textA>,<textB>[,<mode>]` | Compute pairwise similarity (0-1) |
| `semantic;match,<query>,<c1>,<c2>,...[,<mode>]` | Find best match among candidates |

## Example

```
AI:semantic;encode,The winter sea wind in Weihai is strong
→ [0.0123, -0.0456, 0.0789, ...]  (512 dimensions)

AI:semantic;similarity,Weihai winters are cold,The winter sea wind in Weihai is strong
→ {"similarity": 0.87}

AI:semantic;match,The weather is great today,Weihai winters are cold;It rained today;Spring has arrived,3
→ {"best_match": "Spring has arrived", "similarity": 0.72, "index": 2}
```

## Architecture

```
A3 Service extension
  ├── handler.py           — @directive registration + business logic
  ├── schema.json          — directive declarations
  └── text_cli_modules/embed/ — embedding engine (runtime dependency)
```
