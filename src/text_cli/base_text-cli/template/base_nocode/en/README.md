# Bonsai First Aid · English

A self-contained text-cli directive service. Copy the folder and run.

## Files

| File | Purpose |
|------|------|
| `markdown_converter_en.py` | Directive service (change `Domain`/`Action` to repurpose) |
| `Bonsai-First-Aid-Manual_en.md` | Knowledge content — edit this to update the knowledge base |
| `README.md` | This file |

## Start

```bash
python markdown_converter_en.py Bonsai-First-Aid-Manual_en.md
```

Server ready at `http://localhost:8000/text-cli/cli`.

## Query

```bash
# Query a specific symptom
curl -X POST http://localhost:8000/text-cli/cli \
  -H "Content-Type: application/json" \
  -d '{"prompt": "AI:home-gardening;plant-first-aid,Pothos,Yellow Leaves"}'

# List all available plants
curl -X POST http://localhost:8000/text-cli/cli \
  -H "Content-Type: application/json" \
  -d '{"prompt": "AI:home-gardening;plant-first-aid"}'

# View directive schema
curl http://localhost:8000/text-cli/schema

# Health check
curl http://localhost:8000/text-cli/health
```

## Update knowledge

Edit `Bonsai-First-Aid-Manual_en.md`, then restart:

```markdown
## Directive
- Domain: your-domain
- Action: your-action
- Triggers: keyword, another-keyword
- Params: param1, param2

## Knowledge
### Category
#### Sub-category
- Cause: ...
- Treatment: ...
- Prevention: ...
```

Each `###` is a category, `####` a sub-category — append new entries in the same format.

## Change port

```bash
python markdown_converter_en.py Bonsai-First-Aid-Manual_en.md --port 9000
```

Or edit the variables at the top:

```python
Host = "127.0.0.1"
Port = 9000
```

CLI arguments override file variables.

## Change directive

Edit `markdown_converter_en.py`, change the variables at the top:

```python
Domain = "your-domain"
Action = "your-action"
```

Then update `handler()` search logic to match your parameter structure. Restart to apply.

## Token auth

Two variables at the top control request authentication:

```python
AuthEnabled = True          # Require token
ServiceToken = "my-secret"  # Token value
```

Callers must include `Authorization: Bearer <token>`:

```bash
curl -X POST http://localhost:8000/text-cli/cli \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer my-secret" \
  -d '{"prompt": "AI:home-gardening;plant-first-aid,Pothos,Yellow Leaves"}'
```

Wrong or missing token returns `ACCESS_DENIED`. `AuthEnabled=False` (default) allows all.
