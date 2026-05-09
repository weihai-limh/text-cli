# examples/text-cli

指令示例与 Schema 注册表——为人与 AI Agent 提供统一的指令发现入口。

```
text-cli/
├── README.md                    ← 本文件
├── text-cli.json                ← 21 条指令 Schema 聚合（机器消费）
│
├── key/                         ← 密钥管理
│   ├── key_CN.md                ← 指令说明 + curl 示例
│   └── key.py                   ← 实现片段（XOR + 本地加密）
│
├── ai/                          ← AI 辅助
│   ├── ai_CN.md                 ← 推理/视觉 + 回退链说明
│   └── ai.py                   ← 实现片段（多模型回退链）
│
├── embed/                       ← 语义嵌入
│   ├── embed_CN.md              ← 编码/相似/匹配 + 维度说明
│   └── embed.py                 ← 实现片段（cosine + 批量编码）
│
├── mail/                        ← (待补) 邮件
├── 文件/                         ← (待补) 文件
├── git/                         ← (待补) Git
├── system/                      ← (待补) 系统
├── 编码/                         ← (待补) 编码
└── terminal/                    ← (待补) 终端
```

---

## CN · 中文导航

### 基础设施

- [key/key_CN.md](./key/key_CN.md) — 密钥注册/撤销/列表。XOR 传输加密 + 本地二次加密存储。含完整链路示例。

### 智能服务

- [ai/ai_CN.md](./ai/ai_CN.md) — AI辅助推理与视觉。多模型回退链（zhipu/xunfei/modelscope），时段感知路由，零外部依赖。
- [embed/embed_CN.md](./embed/embed_CN.md) — 语义嵌入编码/相似/匹配。embedding-3 在线 API，4 种维度模式，余弦相似度判定。

### 工具链 · 待补

| 域 | 指令数 | 文件 |
|----|--------|------|
| 邮件 | 1 | `mail/mail_CN.md` (待补) |
| 文件 | 4 | `文件/` (待补) |
| Git | 2 | `git/` (待补) |
| 系统 | 2 | `system/` (待补) |
| 编码 | 2 | `编码/` (待补) |
| 终端 | 1 | `terminal/` (待补) |

### Schema 注册表

- [text-cli.json](./text-cli.json) — 全部 21 条指令的 Schema 定义（id/参数/响应/安全策略）。Agent 路由与 Function Calling 的权威源。

---

## EN · English

### Infrastructure

- [key/key_CN.md](./key/key_CN.md) — Key register/revoke/list. XOR transport + local AES encrypt. Complete workflow example. *(Doc in Chinese)*

### Intelligent Services

- [ai/ai_CN.md](./ai/ai_CN.md) — AI reasoning & vision. Multi-model fallback chain (zhipu/xunfei/modelscope), period-aware routing, zero external dependencies. *(Doc in Chinese)*
- [embed/embed_CN.md](./embed/embed_CN.md) — Semantic encode/similarity/match. embedding-3 online API, 4 dimension modes, cosine verdict. *(Doc in Chinese)*

### Toolchain · Pending

| Domain | Directives | File |
|--------|-----------|------|
| Mail | 1 | `mail/` (pending) |
| Files | 4 | `文件/` (pending) |
| Git | 2 | `git/` (pending) |
| System | 2 | `system/` (pending) |
| Codec | 2 | `编码/` (pending) |
| Terminal | 1 | `terminal/` (pending) |

### Schema Registry

- [text-cli.json](./text-cli.json) — 21 directive schemas. Authoritative source for Agent routing & Function Calling.
