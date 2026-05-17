# A8 — 指令发现与聚合入口

不只要"能找到什么指令"，还要"用一个入口收敛多个来源"。

## aggregate 聚合目录

`aggregate/` 下每个 JSON 声明一个聚合域——纯路由表，无执行逻辑：

```json
{
  "id": "map", "type": "aggregate", "domain": "map",
  "default": ["tx-map", "tencent-maps", "gd-map", "bd-map"],
  "providers": {
    "tx-map": {"geocode": "tx-map;geocode"},
    "tencent-maps": {"geocode": "tencent-maps;geocode"},
    "gd-map": {"geocode": "gd-map;geocode"},
    "bd-map": {"geocode": "bd-map;geocode"}
  }
}
```

服务启动时自动扫描加载。提供方来自三种渠道——native handler、MCP 桥、Skill Bridge——聚合引擎不区分类型，只按降级链依次尝试。

## 聚合 dispatch

请求管道最前端插入聚合检查：

```
请求 → 聚合 dispatch → MCP 优先路由 → 本地 dispatch → MCP 后备 → proxy
```

聚合命中 → 遍历 default 降级链 → 每个提供方调 dispatch() → 返回第一个成功结果。配额耗尽自动切下一个，输出格式统一（各提供方适配器保证）。

## 服务清单白名单

`config/service_manifest.json` 控制对外暴露：

```json
{"public_directives": ["map;geocode", "web;search", "weather;query"]}
```

`/skill` 端点只暴露白名单中的指令。默认行为（空数组）= 全部暴露，向后兼容。有内容时只暴露列出的条目——外部调用方只看到聚合入口，看不到原子提供方。
