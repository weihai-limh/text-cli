# A7 — MCP 桥

第 7 级：text-cli ↔ MCP 双向桥。
text-cli 既是 MCP 消费者（调用外部 MCP 工具），也是提供者（暴露指令为 MCP Service）。
依赖：A0-A3

```
A7-mcp/
├── bridge/       ← 正向：text-cli 消费 MCP 工具
├── reverse/      ← 反向：MCP 客户端消费 text-cli 指令（FastMCP）
└── consumer/     ← mcporter handler
```
