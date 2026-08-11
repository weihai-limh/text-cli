# path-str · Path String Utilities

String manipulation primitives for path pipelines. Zero dependencies, stdlib only.

## Install

```
AI:text-cli;install,path-str
```

## Dependencies

None. Python standard library only (`json`, `re`).

## Directives

| Directive | Description |
|-----------|-------------|
| `path-str;template,<template>[,key=value,...]` | Template substitution, supports `{key}` and positional `{0}` `{1}` |
| `path-str;split,'<string>','<delimiter>'` | Split string into array |
| `path-str;join,'<JSON array>','<delimiter>'` | Join JSON array into delimited string |

Chinese aliases: `路径字符串;模板` `路径字符串;切分` `路径字符串;合并`

## Examples

```
AI:路径字符串;模板,你好 {name},{name}=世界
→ {"result": "你好 世界"}

AI:路径字符串;切分,'a;b;c',';'
→ {"parts": ["a","b","c"], "count": 3}

AI:路径字符串;合并,'["a","b","c"]',';'
→ {"result": "a;b;c"}
```

## Architecture

```
Pure Python (stdlib only)
  ├── handler.py    — @directive registration + string operations
  └── schema.json   — 3 directives
```
