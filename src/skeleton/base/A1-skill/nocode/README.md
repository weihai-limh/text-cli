# NoCode — Markdown 经验文档 → text-cli 指令

无需写代码，将结构化的 Markdown 经验文档自动转化为可调用的 text-cli 指令。

## 核心理念

非开发者也能贡献指令。盆栽急救手册是一个花店老板的六篇笔记。markdown_converter.py 把它变成 `AI:家庭园艺;盆栽急救,绿萝,叶片发黄` → 自动返回养护建议。

## 文件

| 文件 | 说明 |
|------|------|
| `markdown_converter.py` | 转化引擎（解析 → 注册 → 服务） |
| `盆栽急救手册.md` | 结构化经验文档示例 |

## 使用

```bash
cd A1-skill/nocode
python markdown_converter.py 盆栽急救手册.md
```

启动后即可通过 `curl http://localhost:8000/text-cli/cli` 调用指令。

## 文档结构要求

```markdown
# 文档标题

## 指令定义
- 领域: <domain>
- 动作: <action>
- 触发词: <keywords>
- 参数: <params>

## 经验内容
### <条目名>
#### <子条目>
- 原因/表现/症状: ...
- 急救/处理: ...
- 预防: ...
```

## 与 cli.py 的关系

`cli.py` 是写代码的 `@register` 路径，`markdown_converter.py` 是写文档的 NoCode 路径。两者殊途同归——最终都生成 SPEC v1.3 兼容的 `schema.json`，通过 text-cli endpoint 暴露为可调用的指令。
