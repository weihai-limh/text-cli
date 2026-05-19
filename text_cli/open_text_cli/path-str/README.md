# path-str

String primitives for path pipeline composition. Zero dependencies, stdlib only.

## Install

```
AI:text-cli;install,path-str
```

## Dependencies

None. Python stdlib only (`json`, `re`).

## Directives

| Directive | Description |
|-----------|-------------|
| `path-str;template,<tmpl>[,key=val,...]` | Template substitution with `{key}` and `{0}` `{1}` positional |
| `path-str;split,'<str>','<delim>'` | Split string into array |
| `path-str;join,'<json-array>','<delim>'` | Join JSON array into delimited string |

## Example

```
AI:path-str;template,Hello {name},{name}=World
→ {"result": "Hello World"}

AI:path-str;split,'a;b;c',';'
→ {"parts": ["a","b","c"], "count": 3}

AI:path-str;join,'["a","b","c"]',';'
→ {"result": "a;b;c"}
```

## Architecture

```
Pure Python (stdlib only)
  ├── handler.py    — @directive registration + string operations
  └── schema.json   — 3 directives
```
