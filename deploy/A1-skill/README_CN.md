# A1 — Agent Skill 封装层

> 将 text-cli 协议级调用封装为 AI Agent 可消费的 Skill。包含意图映射、指令编排、结果加工、降级策略。

## 目录

| 目录 | 内容 | 说明 |
|------|------|------|
| `python/skill.py` | Skill 基类 + `@skill` 装饰器 | 将指令封装为可复用的语义技能 |
| `python/skills/` | 示例：translator、weather | 单指令封装 + 多指令编排示例 |
| `skill/` | Agent Skill 定义模板 | System Prompt 模板、核心调度 Skill |

## python/skill.py

```python
from python.skill import Skill, skill

@skill(domain="天气", action="查询", directive="AI:tc-weather;query,{city}")
class WeatherSkill(Skill):
    def process(self, result):
        return f"城市 {self.params['city']} 的天气：{result}"
```

支持：意图→指令映射、参数提取、结果格式化、错误降级。

## skill/ 下的 Agent 技能定义

| 文件 | 内容 |
|------|------|
| `SKILL.md` | Tide Agent 核心 Skill——元指令调度 + 精品目录 + 多模态渲染 |
| `text-cli-core_CN.md` | 核心调度 Skill v2.0——System Prompt 模板，含 `fetch_available_directives` 和 `text_cli` tool |
| `text-cli-sync-skill.md` | 同步 Skill（冷路径）——端点注册 + 多源拉取 + 聚合写入 |

## 与 A0 的关系

A0 提供零依赖的协议级调用（`call.sh`/`call.ps1`/`call.py`/`call.js`）。A1 在 A0 之上构建 AI 可消费的 Skill 封装——A0 是"怎么调"，A1 是"怎么让 AI 调"。

---

_2026-07-16_
