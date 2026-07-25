# Skill 桥接 — CSV 转 JSON

通过 ClawHub csv2json 技能将 CSV 文件转换为 JSON 数组。委托 copilot Skill Bridge 通用适配器执行。

## 安装

```
AI:text-cli;install,skill-csv2json
```

## 依赖

- 运行时模块：`handlers/skill_bridge`（copilot Skill Bridge 通用适配器）
- ClawHub 技能：`csv2json`
- 无 pip 依赖
- 无需凭据

## 指令

| 指令 | 说明 |
|------|------|
| `skill-csv2json;转换,<输入>` | 将 CSV 文件转换为 JSON 数组 |

## 示例

```
skill-csv2json;转换,/data/records.csv
```

## 架构

```
skill-csv2json/
├── schema.json    ← 指令声明
└── handler.py     ← 委托存根（执行通过 skill_bridge.py）
```

此为 Skill Bridge 包。执行由 copilot Skill Bridge 基础设施处理：
1. 调度匹配 `skill-csv2json` 域 → `SkillBridgeHandlers` mixin
2. `skill_bridge_routes.json` 路由配置映射到 ClawHub 技能 `csv2json`
3. `json_parse` 适配器将输出归一化为 `{status, data}` 格式
