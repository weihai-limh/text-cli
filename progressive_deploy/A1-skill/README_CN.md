# A1-skill — text-cli 调用方工具包

> 让任何 AI Agent 都能调用 text-cli 文本指令。

## 这是什么

`A1-skill` 是 text-cli 协议栈的 A1 层——调用封装。它提供跨语言的客户端实现，让你（AI 或人类开发者）用一行代码或一条命令调用 text-cli 指令。

## 目录

| 模块 | 说明 |
|------|------|
| [`consumer/`](consumer/) | 消费端：调用 text-cli 指令的实现（Shell / Python / JS / NoCode） |
| [`CN/`](CN/) | 中文文档和本地化实现 |

## 指令格式

```
AI:领域;动作,参数1,参数2,...
```

## 快速上手

```bash
# 最简调用（Shell）
cd consumer/shell
echo "AI:tc-datetime;now" | ./call.sh
```

```python
# Python 集成
from consumer.python.call import call_directive
print(call_directive("AI:tc-datetime;now"))
```

## 设计原则

1. **零依赖优先**：Shell 仅需 curl，JS 仅需 Node.js 内置模块
2. **协议即文档**：指令格式 `AI:域;动作,参数` 是人机共读的约定
3. **配置与代码分离**：端点地址和 Token 通过 `conf.json` 声明，不入库
