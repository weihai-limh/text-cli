# examples/test

```
test/
├── README.md                       ← 本文件
│
├── test_token_copilot_CN.md        ← 12 条指令逐条量化 · 文本指令 vs 传统 Agent Token 消耗
├── test_token_paths_CN.md          ← 路径链逐步量化 · path-schema.json 的 Token 价值分析
├── test_tide_weather.md            ← (预留) 在线天气服务测试
│
└── quant_test.py                   ← 可重复运行的量化测试脚本
```

---

## CN · 中文导航

### Token 效率

#### 本地指令

- [test_token_copilot_CN.md](./test_token_copilot_CN.md) — 14 条 text-cli-copilot 指令逐条量化，含与传统 Agent 工具链的同任务对比。核心数据：每条文本指令 ≈ 100 tokens。附审计能力与故障代价压缩分析。
- [test_token_paths_CN.md](./test_token_paths_CN.md) — "查找消息并发送邮件"路径链的 3 步量化，含路径 Schema 的 Token 节约机制分析。

#### 在线服务

- [test_tide_weather.md](./test_tide_weather.md) — (预留) 在线天气服务的端点测试。

---

## EN · English

### Token Efficiency

#### Local Instructions

- [test_token_copilot_CN.md](./test_token_copilot_CN.md) — Per-instruction quantification of 14 text-cli-copilot directives, with side-by-side comparison against traditional agent toolchains. Key finding: ~100 tokens per directive. Includes audit capability and fault-cost compression analysis. *(Report in Chinese)*
- [test_token_paths_CN.md](./test_token_paths_CN.md) — 3-step path chain quantification ("find message → save to file → send email"), with path schema token-saving mechanism analysis. *(Report in Chinese)*

#### Online Services

- [test_tide_weather.md](./test_tide_weather.md) — (Reserved) Online weather service endpoint test.
