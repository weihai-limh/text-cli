# Skill Bridge — CSV to JSON

Convert CSV files to JSON arrays via the ClawHub csv2json skill. Delegates execution to the copilot Skill Bridge universal adapter.

## Install

```
AI:text-cli;install,skill-csv2json
```

## Dependencies

- Runtime module: `handlers/skill_bridge` (copilot Skill Bridge universal adapter)
- ClawHub skill: `csv2json`
- No pip dependencies
- No credentials required

## Directives

| Instruction | Description |
|-------------|-------------|
| `skill-csv2json;convert,<input>` | Convert CSV file to JSON array |

## Example

```
skill-csv2json;convert,/data/records.csv
```

## Architecture

```
skill-csv2json/
├── schema.json    ← directive declarations
└── handler.py     ← delegation stub (execution via skill_bridge.py)
```

This is a Skill Bridge package. Execution is handled by the copilot Skill Bridge infrastructure:
1. Dispatch matches `skill-csv2json` domain → `SkillBridgeHandlers` mixin
2. Route config in `skill_bridge_routes.json` maps to ClawHub skill `csv2json`
3. `json_parse` adapter normalizes output to `{status, data}` format
