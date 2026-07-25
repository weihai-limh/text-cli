# textcli-loader

Zero-dependency text-cli instruction package loader.

Load and execute text-cli packages in any Python environment — no text-cli runtime required.
Works with any AI Agent framework that can `pip install`.

```python
from textcli_loader import load_package, execute

# Load a package
meta = load_package("./my-package/")

# Execute a directive
result = execute("AI:date-calc;add-days,2026-01-01,30")
print(result["rst_data"]["text"])  # → "2026-01-31"
```

## Installation

```bash
pip install textcli-loader
```

Or from source:

```bash
pip install -e .
```

## Usage

### Load and execute

```python
from textcli_loader import load_package, execute

meta = load_package("./my-date-calc/")
print(f"Loaded: {meta['id']}")
for d in meta["directives"]:
    print(f"  AI:{d['domain']};{d['action']}  — {d.get('description', '')}")

result = execute("AI:date-calc;add-days,2026-01-01,30")
print(result)
# → {"rst_types": "text", "rst_data": {"text": "2026-01-31"}, "rst_err": ""}
```

### Use in AI Agent tools

```python
from textcli_loader import load_package, execute

# One-time setup
load_package("./weather-api/")

# Register as tool for any AI Agent framework
def call_textcli_directive(prompt: str) -> dict:
    return execute(prompt)

# AI calls: call_textcli_directive("AI:天气;查询,明天,北京")
```

### Response format

All results use text-cli compatible envelope:

```json
{
    "rst_types": "text",
    "rst_data": {"text": "<result>"},
    "rst_err": ""
}
```

Errors:

```json
{
    "rst_types": "text",
    "rst_data": {"text": "[INVALID_DIRECTIVE_FORMAT] ..."},
    "rst_err": "INVALID_DIRECTIVE_FORMAT"
}
```

## Package format

A text-cli package is a directory with:

```
my-package/
├── schema.json     ← package metadata + directive declarations
└── handler.py      ← Python functions with @directive decorator
```

See [package-dev-guide_zh.md](../base_text-cli/docs/package-dev-guide_zh.md) for the full specification.

## Not supported

- **MCP packages** — require mcporter + MCP server infrastructure
- **Copilot packages** — require copilot runtime (127.0.0.1 sandbox)
- **Path engine** — requires text-cli service runtime
- **Aggregate routing** — requires text-cli service runtime

## Requirements

- Python ≥ 3.10
- Zero external dependencies (stdlib only)

## License

MIT
