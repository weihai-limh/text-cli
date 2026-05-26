# consumer — text-cli 调用方实现

> 让任何 AI Agent 或开发者都能调用 text-cli 文本指令。

## 这是什么

`consumer/` 提供了调用 text-cli 指令的客户端实现。不依赖特定框架，从最简 curl 到语义封装的技能层都有覆盖。

## 指令格式

```
AI:领域;动作,参数1,参数2,...
```

## 调用方式

| 实现 | 目录 | 场景 |
|------|------|------|
| Shell | `shell/call.sh` | 脚本调用、CI/CD、单行测试 |
| Python | `python/call.py` | Python 项目集成，函数式调用 |
| Python | `python/skill.py` | 语义封装：意图→指令映射 + 编排 |
| Node.js | `js/call.js` | Node.js 项目集成，async/await |
| NoCode | `skill/` | Agent 技能定义模板（System Prompt） |

## 配置

每个调用实现目录下都有一个 `conf.json`：

```json
{
  "endpoint": "http://127.0.0.1/cli/text_cli",
  "service_token": "",
  "access_token": ""
}
```

优先级：环境变量 > conf.json > 内置默认值。

| 环境变量 | 对应字段 | 位置 |
|----------|---------|------|
| `TEXT_CLI_ENDPOINT` | endpoint | 请求 URL |
| `TEXT_CLI_SERVICE_TOKEN` | service_token | `Service-token` header（透传 A3） |
| `TEXT_CLI_ACCESS_TOKEN` | access_token | `Authorization: Bearer` header（A5 鉴权） |

空值不发对应 header。

## 快速开始

```bash
# Shell — 通过 stdin 传入指令
cd shell
echo "AI:tc-datetime;now" | ./call.sh
```

```python
# Python
from python.call import call_directive
result = call_directive("AI:tc-datetime;now")
print(result)
```

```js
// Node.js
const { callDirective } = require('./js/call');
const result = await callDirective('AI:tc-datetime;now');
console.log(result);
```

## 端点

| 端点 | 地址 |
|------|------|
| 公共测试端点 | `https://test.text-cli.com/cli/text_cli` |
| 自建端点 | `<自建地址>/cli/text_cli` |

## 安全

- Token 通过环境变量或 `conf.json` 注入，不硬编码
- 超时默认 10 秒
- 空 Token 可发起请求（服务端决定是否放行）
