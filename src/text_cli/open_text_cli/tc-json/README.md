# tc-json

Pure-stdlib JSON structure primitives for path pipelines: validate, pretty-print, list keys, shallow merge, dot-path get/set/del, pick, and text↔JSONL chunking. Zero dependencies.

## Install

```
AI:text-cli;install,tc-json
```

## Directives

| Directive | Description |
|-----------|-------------|
| `tc-json;validate,'<json>'` | Validate JSON; returns `valid` (true/false) with error detail |
| `tc-json;pretty,'<json>'` | Pretty-print with 2-space indent |
| `tc-json;keys,'<json>'` | List all top-level keys of an object |
| `tc-json;merge,'<json1>','<json2>'` | Shallow-merge; keys in json2 override json1 |
| `tc-json;parse,'<json>','<dot-path>'` | Extract value by dot-path (supports array index, e.g. `a.b.0`) |
| `tc-json;set,'<json>','<dot-path>','<value>'` | Set value at dot-path (creates intermediate dicts) |
| `tc-json;del,'<json>','<dot-path>'` | Delete key at dot-path; returns the modified object |
| `tc-json;pick,'<json>','<path-array-json>'` | Extract selected dot-paths into a new object |
| `tc-json;split,'<text>'[,<size>][,<overlap>]` | Split long text into JSONL chunks at sentence boundaries |
| `tc-json;join,'<path>'[,<field>]` | Join JSONL chunks from a file back into a text file |

## Example

```
AI:tc-json;validate,'{"name":"test"}'
AI:tc-json;pretty,'{"a":1,"b":2}'
AI:tc-json;keys,'{"name":"test","age":30}'
AI:tc-json;merge,'{"a":1}','{"b":2}'
AI:tc-json;parse,'{"a":{"b":[1,2,3]}}','a.b.1'
AI:tc-json;set,'{"a":1}','config.timeout',30
AI:tc-json;split,'<long text>',5000
```

## Architecture

```
tc-json/
├── schema.json    — 10 directive declarations
├── handler.py     — JSON primitives + dot-path engine
└── README.md
```

`split`/`join` read and write under the cache directory (`TEXT_CLI_MEDIA_DIR`, fallback `~/.text-cli/media`) and return the resulting file path — handy for feeding large documents into LLM pipelines in bounded chunks.
