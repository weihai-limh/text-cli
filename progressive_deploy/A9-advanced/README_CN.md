# A9 — 高级指令与技能即服务

渐进式部署的最后一层。门面抽象——调用方不需要知道背后有几家提供方、走的是 MCP 还是原生 handler——一个入口收敛所有。

> `all/` 自 A8 累积，内容与 A8 完全相同。`add/` 为空——纯概念层，无新增代码。A9 的价值在聚合降级链的运行时行为，不在部署文件。

## 目录结构

```
A9-advanced/
├── all/                               ← 自 A8 完整复制（相同内容）
│   ├── copilot/                       ← 自 A8 累积
│   ├── service/                       ← 自 A8 累积
│   ├── MCPservice/                    ← 自 A8 累积
│   ├── aggregate/                     ← 自 A8 累积
│   └── media/                         ← 共享基础设施占位
├── add/                               ← 空！纯概念层，无新增代码
├── README_CN.md                       ← 本文档
└── README.md                          ← 已删除
```

## 聚合降级链

`default` 列表定义了降级序。每个提供方按序尝试，成功即返回，失败自动切下一个：

```
map;geocode,威海
  → tx-map;geocode   → 配额耗尽 → 跳过
  → tencent-maps;geocode  → MCP server 不可用 → 跳过
  → gd-map;geocode   → ok → 返回结果
```

降级触发条件：
- dispatch 返回 `{"status":"stop"}`（配额耗尽）
- dispatch 抛异常或返回错误
- 指令未注册（该提供方不支持此 action）

三个条件全部消耗后才返回失败——保证最大可用性。

## 多源统一

聚合不区分来源类型。`map.json` 的提供方列表中，`tx-map` 是 native handler，`tencent-maps` 是 MCP bridge，`skill-bdmap` 是 Skill Bridge。三者在降级链中地位平等。

## 活实例

**地图聚合**：5 提供方降级链，覆盖 geocode/reverse/route/static-map/ip。第一次调用 tx-map 失败 → 自动切 gd-map。调用方只看到 `map;geocode,威海`。

**搜索聚合**：2 提供方（tavily + bd-cloud），统一输出为 tavily 的 answer+sources 格式。`web;search,威海攻略` → 内部自动选择可用的搜索源。

## 认知负担削减

```
之前：Agent 需要知道 tx-map/gd-map/bd-map 三家域名和参数格式
之后：Agent 只需要记住 map;geocode 一个入口
```

新的提供方接入只需在 aggregate JSON 中加一行——不影响任何已有调用方。
