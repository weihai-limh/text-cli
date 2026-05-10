# call — Agent 调用 text-cli 指令

Agent 集成 text-cli 指令的客户端实现。不依赖特定框架，提供从最简 curl 到完整 SDK 的多层方案。

## 指令格式（不可变协议）

```
AI:领域;动作,参数1,参数2,...
```

## 多层调用方案（按实现方式组织）

| 层级 | 路径 | 适用场景 |
|------|------|---------|
| Python | `python/call.py` | Python 项目集成，函数式调用 |
| Python | `python/skill.py` | 语义封装：意图→指令映射 + 编排 + 降级 |
| JS | `js/call.js` | Node.js 项目集成，async/await + 批量调用 |
| Shell | `shell/call.sh` | curl 直接调用，单行测试，CI/CD |
| (Python | `python/client.py` | 需要重试/超时/多端点管理的场景 → 待实现) |
| NoCode | `CN/call/nocode/` | Agent 技能定义模板（System Prompt + 工具描述） |

### Python 技能层

技能是对 text-cli 指令的**语义封装**。它把一个意图（"查询天气"）映射到一条或多条指令，加上结果格式化和错误降级，形成可复用的能力模块。

```python
from call.python.skill import Skill, skill

@skill("天气查询", domain="天气", action="查询")
class WeatherSkill(Skill):
    def format_result(self, raw, params):
        return f"🌤️ {params[0]}: {raw}"

    def on_error(self, params, error):
        return f"暂时无法查询{params[0]}的天气"

# 一行调用
result = WeatherSkill.run("威海", "明天")
print(result.text)  # 🌤️ 明天威海: 晴, 15-22°C
```

**预置技能**（`skills/`）：

| 技能 | 类型 | 说明 |
|------|------|------|
| `WeatherSkill` | 单一技能 | 封装单条指令，格式化 + 降级 |
| `TranslatorSkill` | 复合技能 | 编排多指令（检测语言 → 翻译 → 格式化），非关键步骤静默降级 |

**技能 vs 原始调用**：

```
原始调用:   call_directive("AI:天气;查询,威海,明天")
技能调用:   WeatherSkill.run("威海", "明天")

区别:       技能封装了端点选择、错误兜底、结果格式化
           使用者不需要知道"AI:天气;查询"这个格式
```

## 端点

| 端点 | 地址 | 鉴权 |
|------|------|------|
| 公共测试端点 | `https://test.text-cli.com/cli/text_cli` | Access Token |
| 自建端点 | `<自建地址>/cli/text_cli` | Service Token |

## 典型调用流程

```
Agent 收到用户意图
    ↓
将意图映射为 AI:领域;动作
    ↓
调用 HTTP POST /cli/text_cli
    ↓
解析响应 rst_data.text
    ↓
将结果返回用户 / 进入下一步推理
```

## 安全

- Access Token / Service Token 通过环境变量注入，绝不硬编码
- 单次调用超时默认 10 秒
- 返回文本直接使用，不做自动执行
