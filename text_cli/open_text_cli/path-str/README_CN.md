# path-str · 路径字符串

路径管道组合用的字符串基础操作。零依赖，仅标准库。

## 安装

```
AI:text-cli;install,path-str
```

## 依赖

无。仅 Python 标准库（`json`、`re`）。

## 指令

| 指令 | 说明 |
|------|------|
| `path-str;template,<模板>[,键=值,...]` | 模板替换，支持 `{key}` 和 `{0}` `{1}` 位置参数 |
| `path-str;split,'<字符串>','<分隔符>'` | 切分字符串为数组 |
| `path-str;join,'<JSON数组>','<分隔符>'` | JSON 数组合并为分隔字符串 |

中文别名：`路径字符串;模板` `路径字符串;切分` `路径字符串;合并`

## 示例

```
AI:路径字符串;模板,你好 {name},{name}=世界
→ {"result": "你好 世界"}

AI:路径字符串;切分,'a;b;c',';'
→ {"parts": ["a","b","c"], "count": 3}

AI:路径字符串;合并,'["a","b","c"]',';'
→ {"result": "a;b;c"}
```

## 架构

```
纯 Python（仅标准库）
  ├── handler.py    — @directive 注册 + 字符串操作
  └── schema.json   — 3 条指令
```
