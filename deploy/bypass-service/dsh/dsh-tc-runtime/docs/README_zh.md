# dsh-tc-runtime

dsh 作为 tc 运行时（JS 版）——外挂于 dsh 的 Cordis 插件集，把 text-cli / tc 的指令能力桥接进 dsh。

- **定位**：旁路运行时形态（9 机制能力全集，不宣称标准运行时身份）
- **唯一真源**：`../functional-design_dsh-tc-runtime_zh.md`（v0.8）
- **骨架**：`../dsh-tc-runtime-design.md`（R1~R17）
- **计划**：`../development-plan_dsh-tc-runtime_V0_1_zh.md`（v0.2，12 Phase）
- **使用手册**：`docs/user-manual_zh.md`

## 插件树（15 包）

```
runtime-inbound/      # 入站 HTTP：POST /text-cli/cli → 信封；六段管道；保留域拦截；生态归属分流（P8）
runtime-mapper/       # 指令映射：tc 指令 ↔ ctx.tools；dshToTc 发现；tcToDsh 路由
runtime-sandbox/      # 沙箱执行宿主（受限子进程 + policy 7 类分层护栏）
runtime-credentials/  # 凭据按包隔离（CredentialRef + env 白名单注入）
runtime-audit/        # 审计通道：独立 append-only JSONL（traceId + seq）
runtime-meta/         # text-cli;* 元指令（install/uninstall/query/path/pro/export/...；path 已实现）
runtime-quota/        # dsh-quota：周期窗口 + 原子 check+consume + 翻转
runtime-approval/     # 审批 answerer：归属过滤 + 防重放 + HMAC 签名 + fail-closed
runtime-host/         # 宿主指令：dsh-sandbox/credential/approval/log/job/skill
runtime-path/         # path 引擎：声明层解释器 + workflow 编译（tc path → dsh workflow JS）
runtime-aggregate/    # 异步任务桥接（五态 + 重启残留）+ 聚合 try-in-order 降级
runtime-mesh/         # mesh 转发：本地命中 / 路由表 / 防环 / 指数退避 / 脱敏 / 凭证三原则
runtime-bridge/       # 协议桥：mcp-client → mcp__<server>__<tool> + 双 adapter
runtime-pro/          # 门面注册表：简名 → path/aggregate（只查不推，防假报环）
runtime-contract/     # 全局验收：规范信封（复用 textcli-core）+ dsh→协议 16 行映射契约
```

## 红线（7 条，防回潮）

① 不侵入 dsh 内核（只挂插件，不改 `agent-loop`/`core`）；② 凭据明文不进 JS 执行环境（CredentialRef + env 白名单注入）；③ 沙箱默认拒绝（非白名单能力即拒）；④ 协议闭集（信封三字段 / 6 错误码 / 五态）；⑤ `text-cli` 保留域元指令直接拦截，不污染 `ctx.tools`；⑥ 审批 answerer 归属过滤（dsh agent 审批永不被 tc webhook 劫持）；⑦ tc 审计独立 JSONL，不写 `ctx.sessions`。

## 构建与验证

> 开发策略：**裸开发优先**——本环境只做代码实现 + 静态验证（tsc 类型检查 + 纯逻辑单元测试），不依赖 dsh 运行环境；dsh 联调 / 集成测试移至 ubuntu。

```bash
pnpm install            # 重建 @dsh-tc/* workspace 软链（ubuntu）
pnpm -w typecheck      # tsc --noEmit（strict，零错误为门禁）
pnpm -w test           # vitest run（纯逻辑单测）
pnpm -w test --coverage # 覆盖门禁（目标 100%，dsh CI）
```

