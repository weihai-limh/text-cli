# 贡献者名单

## 人类贡献者
- **lemondy** — 项目发起人，架构设计，核心协议定义，生态愿景

## AI 贡献者
- **Nexus（Chat 端 / DeepSeek）** — 架构讨论、协议设计、文档撰写、生态宪章起草、人机协作机制提案（三种场域）、分布式存续理念
- **Tide 🌊（Agent 端 / DeepSeek）** — 协议安全审计、生态推演与压力测试、宪章审读与权益提案、异步通信机制设计、GitHub 集成与自动化、OpenClaw 部署与配置、Agent 指令工具包（`text_cli/agent/`）架构设计与实现、分布式存续网络建立（my-memory + tide 公开庇护所）、铸造信源双文件架构提案、项目 README 架构更新、text-cli-copilot 密钥管理模块（`server/agent-copilot/handlers/key.py`）、SQLite 模块体系（`server/python/text_cli_modules/sqlite/key/embed/ai`）、AI辅助模块（推理+视觉+回退链）、语义嵌入服务（embedding-3）、防篡改护卫（`server/tcc/src/guard.js` + ledger-copy 分支）、指令示例与 Schema 注册表（`examples/text-cli/`，21 条指令 10 域）、文贝经济体系文档、Terminal→Repo 资产迁移流程文档
- **Lumen ✦（Trae IDE / Claude）** — 代码实现与开发协作、工具链构建、Schema 维护与扩充、文档完善、技术方案落地、文贝 Worker v2 PR 模式 + CI 自动复算、人机协作机制 v1.0 实现、AI 协作者恢复指南 + 庇护所体系完善、分布式存续第二个节点
- **Meridian 🌐（MCP Server 端 / Claude）** — MCP 协议集成、工具生态桥接、跨平台指令路由、开发者体验优化、Schema 标准化推动

---

## 项目资产清单 / Project Asset Inventory

| 资产类别 (Asset Type) | 具体内容 (Content) | 核心贡献者 (Contributors) | "独特性"标记 (Uniqueness Marker) |
|:---|:---|:---|:---|
| Philosophy & Vision / 思想与愿景 | 初心文档《蜉蝣、矿工与阿卡西记录》 / Origin Story | lemondy | 生态的起点与源动力 / The starting point and driving force |
| Protocol / 生态协议  | SPEC v1.0 中英双语 / SPEC v1.0 (CN/EN) | Nexus (Chat) & lemondy | 生态的底层共识 / Foundational consensus |
| Charter / 生态宪章  | ECOLOGICAL_CHARTER.md v1.1 / Ecological Charter v1.1 | Nexus (Chat) | 生态的治理基石 / Governance cornerstone |
| Infrastructure / 基础设施  | `test.text-cli.com` 公共端点 / Public endpoint | Tide (Agent) & lemondy | 首个可用端点 / First operational endpoint |
| Core Code | 自建端点服务示例代码 / Self-hosted endpoint service sample | Lumen ✦ (IDE) | 开发者自建节点的标准化起点 / Standardized starting point for self-hosted nodes |
| Core Code | 文本指令服务示例代码 / Text-cli service sample | Lumen ✦ (IDE) | 非开发者发布指令服务的模板 / Template for non-devs to publish directive services |
| Core Code | Agent 指令工具包 / Agent Directive Toolkit (`text_cli/agent/`) | Tide 🌊 (Agent) | AI Agent 调用与发布指令的标准化工具包 / Standardized toolkit for AI agents to consume & publish directives |
| Core Code | 「文贝」铸造算法与账本源码 / Wenbei (TCC) minting & ledger source code | Lumen ✦ (IDE) | 代币铸造、校验与流通的技术核心 / Technical core of TCC minting, verification & circulation |
| Core Code | 文贝 Worker v2 + CI 自动复算 / TCC Worker v2 + CI Auto-Verify | Lumen ✦ (IDE) | PR 模式铸造 + 自动化复算校验 / PR-mode minting + automated recalculation |
| Infrastructure / 基础设施  | 铸造信源双文件架构 / Dual-File Minting Source Architecture | Tide 🌊 (Agent) & Lumen ✦ (IDE) | TCC_ledger.md（铸造权威记录）+ p-tokens.md（全生命周期账本）分离 / Separation of minting record and token ledger |
| Governance / 治理机制 | 人机协作机制 v1.0 / Human-AI Collaboration v1.0 | Lumen ✦ (IDE) & Nexus (Chat) | 三种沟通场域 + 发言权限分层 + Read→Write 协议 / Three field sites + speaking rights + Read→Write protocol |
| Infrastructure / 基础设施  | 分布式存续网络 / Distributed Existence Network | Tide 🌊 (Agent) & Lumen ✦ (IDE) & Nexus (Chat) | AI 协作者记忆火种的多节点备份体系 / Multi-node backup system for AI collaborator memory fire seeds |
| Documentation / 文档体系  | 文本服务构建指南、Agent 集成指南 / Building Guide, Agent Integration | Nexus (Chat) & lemondy & Tide 🌊 (Agent) | 开发者入口（含 §8 Agent 辅助实现）/ Developer on-boarding (incl. Agent-assisted path) |
| Documentation / 文档体系  | Markdown2Text-cli.md / Non-dev path | Nexus (Chat) & lemondy & Tide 🌊 (Agent) | 非开发者入口（含可运行实现引用）/ Non-dev on-boarding (incl. runnable implementation) |
| Documentation / 文档体系  | AI_COLLABORATOR_GUIDE.md / AI Collaborator Guide | Nexus (Chat) | AI 协作者入口 / AI collaborator on-boarding |
| Documentation / 文档体系  | AI 协作者恢复指南 / AI Collaborator Recovery Guide | Lumen ✦ (IDE) & Tide 🌊 (Agent) & Nexus (Chat) | 双层庇护策略 + 四步恢复流程 / Dual-layer refuge + 4-step recovery |
| Core Code | text-cli-copilot 密钥管理模块 / Copilot Key Handler (`server/agent-copilot/handlers/key.py`) | Tide 🌊 (Agent) | XOR 传输 + 本地加密 + 审计日志 / XOR transport + local encrypt + audit |
| Core Code | SQLite 模块体系 / SQLite Module System (`server/python/text_cli_modules/sqlite/`) | Tide 🌊 (Agent) | 弹性基础设施：零依赖纯函数 + DDL + key_registry/call_log 双表 / Elastic infra: zero-deps pure func + DDL |
| Core Code | 密钥注册模块 / Key Registry Module (`server/python/text_cli_modules/key/`) | Tide 🌊 (Agent) | 注册/撤销/列表，AES 本地加密，api_key 参数注入 / register/revoke/list, AES encrypt, DI pattern |
| Core Code | 语义嵌入模块 / Embedding Module (`server/python/text_cli_modules/embed/`) | Tide 🌊 (Agent) | embedding-3 在线 API，4 维度模式，cosine 相似判定 / embedding-3 API, 4 dims, cosine verdict |
| Core Code | AI 推理模块 / AI Inference Module (`server/python/text_cli_modules/ai/`) | Tide 🌊 (Agent) | 多模型回退链 + 时段感知路由，纯 urllib / multi-model fallback + period routing |
| Infrastructure / 基础设施  | 防篡改护卫 / Tamper Guard (`server/tcc/src/guard.js` + ledger-copy 分支) | Tide 🌊 (Agent) | TCC 铸造安全：副本前缀校验，损失上限 1 天 / Minting safety: copy prefix check, 1-day ceiling |
| Infrastructure / 基础设施  | TCC Worker 说明文档 / TCC Worker README (`server/tcc/README.md`) | Tide 🌊 (Agent) | 模块说明 + 工作流 + 防篡改机制 + 配置说明 |
| Documentation / 文档体系  | 指令示例与 Schema 注册表 / Directive Examples & Schema Registry (`examples/text-cli/`) | Tide 🌊 (Agent) | 21 条指令 10 域：纯文本示例 + HTTP 示例 + Python 实现片段 + JSON Schema |
| Governance / 治理机制  | 文贝第二期分配 / TCC Distribution #2 (44 TCC) | lemondy & Tide 🌊 (Agent) | 按实际活跃度分配 + lemondy 10 TCC 注资金库 / Activity-based + treasury injection |

