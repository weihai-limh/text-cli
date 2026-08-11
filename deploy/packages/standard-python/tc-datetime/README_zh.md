# tc-datetime — 日期时间计算

> 路径管道用日期时间计算工具。零外部依赖，纯 stdlib datetime + calendar。

---

## 指令

### now — 当前时间

```
tc-datetime;now          → ISO 格式
tc-datetime;now,human    → 人类可读
tc-datetime;now,date     → 仅日期
tc-datetime;now,timestamp → Unix 时间戳
```

### offset — 日期偏移

```
tc-datetime;offset,2026-05-20,{"days":3}
tc-datetime;offset,2026-05-20,{"weeks":1,"days":2}
tc-datetime;offset,2026-05-20,{"months":1}
```

支持：`days` `weeks` `months` `years` `hours` `minutes`（可负数）。月偏移月末安全。

### between — 日期间距

```
tc-datetime;between,2026-01-01,2026-05-20,days    → 139
tc-datetime;between,2026-01-01,2026-05-20,human   → "4个月19天"
```

单位：`days` `hours` `minutes` `seconds` `human`。

### weekday — 星期几

```
tc-datetime;weekday,2026-05-20
→ {"weekday":"星期三","weekday_en":"Wednesday","weekday_num":2,"is_weekend":false}
```

### range — 日期序列

```
tc-datetime;range,2026-05-20,{"days":7}              → 未来 7 天
tc-datetime;range,2026-05-20,{"until":"2026-06-01","step":3}  → 每 3 天到 6 月 1 日
```

### format — 格式互转

```
tc-datetime;format,1779000000,human
tc-datetime;format,2026-05-20T17:30:00,date
```

目标格式：`iso` `date` `timestamp` `human` `human_en`。

---

## 管道示例

```
tc-datetime;now
  → tc-json;parse,<上一步>,date
  → tc-datetime;offset,<上一步>,{"days":3}
  → {"result":"2026-05-23","weekday":"星期六"}
```
