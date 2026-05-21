# A4 — Paths (指令路径)

> Path is text-cli's orchestration layer.
> It composes atomic directives into declarative, fault-tolerant pipelines.

`all/copilot/` + `all/service/` 自 A3 累积。本层新增：引擎版 `text_cli_path.py` 替换骨架版，增加国际化消息配置。

路径示例、技能市场、Schema 注册表已迁出至项目顶级目录 `examples/paths/` 和 `registry/paths/`。

---

## 定位

| 问题 | 答案 |
|------|------|
| 路径是什么 | 将原子指令编排为声明式、可容错的执行管道 |
| 路径解决什么 | "做一件事需要多步，哪步先哪步后，失败了怎么办" |
| 指令回答什么 | "这一个具体操作怎么做" |
| 边界 | 路径编排"做什么"，指令实现"怎么做" |
| 复杂度上限 | 瞬时思考的深度——两次降级就是深度上限 |

路径不是图灵完备的编程语言。它是有序的、可读的、可调试的配方——人和 AI 都能读、能生成、能执行。

---

## Pre-A4 → Post-A4

```
Pre-A4                          Post-A4
──────────────────────────────────────────
路径 = JSON 声明                 路径 = 引擎执行
AI 读 JSON 理解步骤             引擎解析 if/degradation/timeout
编排负担在 AI                   编排负担转移到引擎
"我做 geocode 然后 offset"      "geocode 失败→降级→超时→断路"
```

两个时代共存。没有 `if` 的路径 AI 仍能通过原生理解力执行。有 `if` 的路径引擎接管容错编排。Post-A4 是 Pre-A4 的超集。

---

## 目录结构

```
A4-paths/
├── all/                               ← 本层完整可部署产物
│   ├── copilot/                       ← 自 A3 累积
│   ├── service/                       ← 自 A3 累积 + A4 新增
│   │   ├── handlers/
│   │   │   └── text_cli_path.py       ← 引擎版（替换 A3 骨架版）
│   │   └── config/
│   │       ├── path_messages_cn.json  ← A4 新增 — 中文消息模板
│   │       └── path_messages_en.json  ← A4 新增 — 英文消息模板（规范 + fallback）
│   └── media/                         ← 共享基础设施占位
├── add/                               ← A4 纯增量
│   └── service/
│       ├── handlers/
│       │   └── text_cli_path.py       ← 引擎版
│       └── config/
│           ├── path_messages_cn.json
│           └── path_messages_en.json
└── README_CN.md                       ← 本文档
```

## 已迁出资产

以下文件已移至项目顶级目录：

| 原位置 | 现位置 | 说明 |
|--------|--------|------|
| `examples/` | `examples/paths/` | 路径示例（如 geo_panoramic_query.json） |
| `marketplace/` | `examples/paths/marketplace/` | 技能市场（photo-analysis 等） |
| `registry/` | `registry/paths/` | 路径 Schema 注册表（path-schema.json） |

---

## 快速开始

### 运行示例路径

```
AI:text-cli;path,examples/paths/geo_panoramic_query.json,威海
```

### 使用条件分支

```json
{
  "id": "visual",
  "directive": "geo-panoramic;china,{coord.0},{coord.1}",
  "output_as": "panorama",
  "if": {"step": "road", "field": "status", "equals": "ok"},
  "degradation": [
    {"id": "fallback", "directive": "bd-map;static-map,{lon},{lat},16"}
  ]
}
```

### 路径语言切换

```json
{"lang": "cn", ...}  // 中文消息
{"lang": "en", ...}  // 英文消息（默认）
```

---

## 能力总览

| 层 | 能力 | 语法 |
|:--:|------|------|
| L0 | 断路保护 | 引擎内置 |
| — | timeout 时间守卫 | `"timeout": <ms>` |
| L1 | 条件分支 | `"if": {...}` + equals/contains/matches/exists |
| — | 降级递补 | `"degradation": [...]` |
| L2 | 并行执行 | `"mode": "parallel"` + first_ok/all |
| L2 | 函数表达式 | count/size/exists + eq/gt/lt/gte/lte/ne |

---

## 依赖

- A3：服务端点（`/cli/text_cli` 入口）
- A3 累积：copilot 本地代理 + service 平台核心

---

## 相关文档

- 路径语法完整设计：`tide-scripts/other_MD/path-syntax-2026-05-16_CN.md`
- 实施计划与记录：`tide-scripts/other_MD/path-engine-v1-implementation-plan_CN.md`
- 路径市场：`examples/paths/marketplace/`
- 路径 Schema 注册表：`registry/paths/`
