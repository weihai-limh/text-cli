# tc-table — 表格数据处理

> 路径管道用表格数据处理工具。读文件 → JSON数组 → 筛选/排序/透视/合并 → 写回。
> CSV/TSV 零外部依赖。XLSX 可选 openpyxl。

---

## 指令

### read — 读取文件

```
tc-table;read,data.csv
tc-table;read,data.tsv,tsv
tc-table;read,data.xlsx
```

返回 `{rows, columns, count, source, format}`。格式自动从扩展名推断。

### schema — 列结构

```
tc-table;schema,data.csv
```

返回每列的 `name`、`inferred_type`（string/number）、`sample_values`（前 3 行）。

### filter — 筛选行

```
tc-table;filter,<JSON数组>,{"where":["列名","运算符","值"],"limit":10}
```

| 运算符 | 说明 |
|--------|------|
| `=` `!=` | 等于/不等于 |
| `>` `<` `>=` `<=` | 数值比较 |
| `contains` | 字符串包含 |
| `starts` `ends` | 开头/结尾 |
| `in` | 值在逗号分隔列表中 |

### sort — 排序

```
tc-table;sort,<JSON数组>,{"by":"age","dir":"desc"}
tc-table;sort,<JSON数组>,{"by":["city","age"],"dir":["asc","desc"]}
```

### pivot — 分组聚合

```
tc-table;pivot,<JSON数组>,{"group":"city","agg":"count"}
tc-table;pivot,<JSON数组>,{"group":"city","agg":"sum","on":"amount"}
```

聚合函数：`count`/`sum`/`avg`/`min`/`max`。

### join — 两表合并

```
tc-table;join,<表A>,<表B>,{"on":"city","type":"left"}
```

类型：`inner`(默认)/`left`/`right`/`outer`。同名列右表加 `_right` 后缀。

### write — 写回文件

```
tc-table;write,<JSON数组>,output.csv
tc-table;write,<JSON数组>,output.xlsx,xlsx
```

CSV: UTF-8 with BOM。XLSX: 需 `openpyxl`。

---

## 管道示例

```
tc-table;read,sales.csv
  → tc-table;filter,<上一步>,{"where":["amount",">","200"]}
  → tc-table;sort,<上一步>,{"by":"amount","dir":"desc"}
  → tc-table;write,<上一步>,top_sales.csv
```
