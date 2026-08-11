# tc-datetime — Date-Time Calculations

> Date/time calculation tools for path pipelines. Zero external dependencies, pure stdlib datetime + calendar.

---

## Directives

### now — Current time

```
tc-datetime;now          → ISO format
tc-datetime;now,human    → human readable
tc-datetime;now,date     → date only
tc-datetime;now,timestamp → Unix timestamp
```

### offset — Date offset

```
tc-datetime;offset,2026-05-20,{"days":3}
tc-datetime;offset,2026-05-20,{"weeks":1,"days":2}
tc-datetime;offset,2026-05-20,{"months":1}
```

Supports: `days` `weeks` `months` `years` `hours` `minutes` (negative allowed). Month-end safe.

### between — Duration between dates

```
tc-datetime;between,2026-01-01,2026-05-20,days    → 139
tc-datetime;between,2026-01-01,2026-05-20,human   → "4个月19天"
```

Units: `days` `hours` `minutes` `seconds` `human`.

### weekday — Day of week

```
tc-datetime;weekday,2026-05-20
→ {"weekday":"星期三","weekday_en":"Wednesday","weekday_num":2,"is_weekend":false}
```

### range — Date sequence

```
tc-datetime;range,2026-05-20,{"days":7}              → next 7 days
tc-datetime;range,2026-05-20,{"until":"2026-06-01","step":3}  → every 3 days until Jun 1
```

### format — Format conversion

```
tc-datetime;format,1779000000,human
tc-datetime;format,2026-05-20T17:30:00,date
```

Target formats: `iso` `date` `timestamp` `human` `human_en`.

---

## Pipeline Example

```
tc-datetime;now
  → tc-json;parse,<step>,date
  → tc-datetime;offset,<step>,{"days":3}
  → {"result":"2026-05-23","weekday":"星期六"}
```
