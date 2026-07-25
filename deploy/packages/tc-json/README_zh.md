# tc-json 结构操作

JSON 结构原语工具：校验、美化、列出键、浅合并、点路径解析。

## 安装

```
AI:text-cli;install,tc-json
```

## 依赖

零依赖（纯 Python stdlib）。

## 指令

| 指令 | 说明 |
|------|------|
| `tc-json;校验,'<json>'` | 校验 JSON 合法性 |
| `tc-json;美化,'<json>'` | 美化输出（2 空格缩进） |
| `tc-json;所有键,'<json>'` | 列出 JSON 对象所有顶层键 |
| `tc-json;合并,'<json1>','<json2>'` | 浅合并（json2 覆盖 json1） |
| `tc-json;解析,'<json>','<点路径>'` | 点路径提取值（支持数组索引） |

## 示例

```
AI:tc-json;校验,'{"name":"test"}'
AI:tc-json;美化,'{"a":1,"b":2}'
AI:tc-json;所有键,'{"name":"test","age":30}'
AI:tc-json;合并,'{"a":1}','{"b":2}'
AI:tc-json;解析,'{"a":{"b":[1,2,3]}}','a.b.1'
```

## 架构

```
tc-json/
├── schema.json
├── handler.py
└── README_CN.md
```
