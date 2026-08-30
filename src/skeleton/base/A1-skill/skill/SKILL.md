---
name: text-cli
description: text-cli multi-endpoint dispatch — discover, call, and degrade across trusted service endpoints
type: permanent
---

# text-cli Agent Skill

You are an AI agent equipped with the text-cli protocol SDK. Your core directive loop:

1. **Discover** — `from python.call import discover` → get available directives
2. **Call** — `from python.call import call` → DirectiveResult(ok, data, is_async)
3. **Degrade** — A1 handles multi-endpoint fallback automatically through `Skill.run()`

## Quick Start

```python
import sys; sys.path.insert(0, "python")
from call import call, discover

# Find available directives
directives = discover()
# → [{"domain":"weather","action":"query","usage":"weather;query,<city>,<date>"}]

# Call a directive — always returns immediately
result = call("AI:weather;query,tomorrow,Beijing")
# → DirectiveResult(ok=True, data={"temp":"12-18C"}, is_async=False)

# Async tasks
if result.is_async:
    from call import poll
    status = poll(result.task_id)
```

## Endpoint Configuration

Edit `config/agent-endpoints.json` to add trusted endpoints, then sync:

```bash
cd python && python aggregation.py sync
```

## Files

| File | Purpose |
|------|------|
| `python/call.py` | A0 SDK — zero-dependency text-cli client |
| `python/call.js` | A0 SDK — JavaScript version |
| `python/skill.py` | A1 Skill base — @skill decorator + degradation |
| `python/aggregation.py` | Endpoint registration + sync tool |
| `python/cli.py` | Compile path — @register → schema.json |
| `prompts/SKILL.md` | Detailed dispatch rules |
| `prompts/text-cli-core_zh.md` | Core dispatch v2.0 System Prompt |
| `config/` | Endpoint registry + aggregation schema |
