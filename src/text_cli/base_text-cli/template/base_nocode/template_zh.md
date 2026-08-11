# {TITLE}

<!--
  以下字段标签使用中文（zh）。
  解析器是语言无关的：在 converter_template.py 的 FIELD_LABELS 中添加你的语言后，
  即可使用该语言的标签。
  字段值（":" 后的文本）和正文内容可以使用任意语言。
-->

## 指令定义
- 领域: {DOMAIN}
- 动作: {ACTION}
- 触发词: {TRIGGERS}
- 参数: {PARAM_1}, {PARAM_2}
- 来源: {SOURCE}                  # 可选 — 知识的出处
- 核实: {VERIFIED}                # 可选 — 核实人与日期，格式：核实人,YYYY-MM-DD
- 过期: {STALE_AFTER}             # 可选 — 过期日期，YYYY-MM-DD
- 状态: {STATUS}                  # 可选 — draft | stable | deprecated

## 经验内容
<!--
  以下内容字段为约定写法，解析器不做特殊处理。可使用任意语言。
-->

### {CATEGORY_1}
#### {SUB_1}
- 原因: ...
- 处理: ...
- 预防: ...
- 鉴别: ...                         # 可选 — 如何与相似问题区分
- 教训: ...                         # 可选 — 血泪教训

### {CATEGORY_2}
#### {SUB_2}
- 原因: ...
- 处理: ...
- 预防: ...
- 鉴别: ...
- 教训: ...

---
> {FOOTER}
