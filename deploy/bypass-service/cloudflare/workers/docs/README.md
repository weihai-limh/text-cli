# Cloudflare 专供版旁路运行时（textcli-core-cloudflare）

> 策划稿：`cloudflare-bypass-runtime_zh.md`（v0.1）｜协议宪法：`text-cli/docs/SPEC_zh.md` v1.3.2
> 共享逻辑层：`../tc-js-skeleton`（13 组件 / 84 测试）

**定位**：不是 tc-js-skeleton 的移植，也不是第二份实现——是**共享同一套逻辑组件 + 三个平台适配器**。
逻辑层（协议/编排/护栏/鉴权/存储契约）唯一一份，平台面（Worker 入口 / D1 受限执行 / D1 持久化）各写各的。

## 架构（洋葱 外→内）

```
入口/鉴权面    Worker fetch → 校验 Service-token → 端点表面（/cli /tasks/{id} /skills /health）
编排层         withAuth → withCfMesh → withPath → withUsage → withAudit → withNativeGuard
执行层         D1 可执行包（schema + handler 源码字符串）→ 受限执行（分级能力注入）
持久层         D1：kv / packages / tokens / keys / usage / tasks / audit / mesh_peers / mesh_routes / service_manifest
```

## 复用 vs 新写

| 复用（tc-js-skeleton 组件，零改动） | 新写（本目录） |
|---|---|
| `contract`（信封/闭集）、`guard`（共享 ancestorChain）、`path`（instruction 模板编排 + 注册发现）、`auth`（Service-token）、`audit`（trace）、`storage`（createStorage/namespace 契约）、`credentials` 思路、`mesh` 思路 | `src/d1-storage.js`（D1→StorageKV）、`src/executor.js`（D1 源码受限执行+分级 sandbox）、`src/meta.js`（D1 可执行包生命周期 + **别名注册**）、`src/token.js`/`key.js`/`usage.js`/`tasks.js`/`mesh.js`（指令面）、`src/endpoints.js`+`src/index.js`（Worker 入口） |

## 能力清单（对齐策划 §三）

- **协议面**：`POST /text-cli/cli` + `GET tasks/{id}`（五态）+ `GET skills`（白名单）+ `GET health`（机制声明）+ GET 应急通道（默认关）
- **D1 可执行包**：`text-cli;install/uninstall/packages/query`——handler 源码字符串存 D1，受限构造执行，真·热装
- **受限执行**：`new Function` 构造，分级 sandbox（pure 无通道 / network 有 fetch / config-inject 有 credential / network-credential 全有），凭据按包 capability 白名单
- **Service-token**：`token;issue/revoke/list`，运行时=能力提供方，单 token 闭环，拒绝→`SERVICE_DENIED`；入口强制（跨终端合规 §6.1）
- **请求方计次**：`quota;register` + 挂 requester_id 周期计次，耗尽→`status:stop` 降级信号（非错误）
- **key 指令化凭据**：`key;register/revoke/list`，AES-GCM 加密落 D1（明文不落盘），`sandbox.credential.get` 注入
- **编排**：path 声明式流水线（**instruction 字符串模板**，对齐协议 SPEC §4：插值/if/degradation/parallel/map/source 跨节点 + 五入口 `--register/--json/inline-json/file/name` + 注册进 query 发现）+ 环检测（native/path 共享链）+ mesh 代理
- **异步任务**：D1 tasks 五态（pending/running/done/error/cancelled），重启对账 running→error+service_restarted
- **mesh 代理**：`mesh;peer-register/route-add/peer-list`，本地不命中→mesh_routes→peer 双 token 转发（凭证按 peer 隔离）

## 目录

```text
Cloudflare-Workers/
├── cloudflare-bypass-runtime_zh.md   # 策划稿
├── schema.sql                        # D1 建表（9 表 + kv）
├── packages-src/                     # 内置包源（weather / tc-math，Worker 兼容 handler 格式）
├── src/                              # 平台面（入口/执行/持久化/指令面）
├── test/                             # 17 用例（D1 mock：mini SQL 引擎，零删除）
└── package.json
```

## 运行与测试

```bash
# 测试（无需网络/无 wrangler；D1 用内存 mock 走真实代码路径）
node --test test/*.test.js        # 18/18（含 path instruction 模板编排 + 别名路由回归）

# 回归：共享逻辑层不受影响
cd ../tc-js-skeleton && node --test test/*.test.js   # 91/91
```

**真实部署**（有网络时）：
1. `wrangler d1 create tc-bypass`，`wrangler d1 execute tc-bypass --file=schema.sql`；
2. `wrangler.toml` 绑定 `DB`（D1）+ secrets `AUTH_SECRET` / `KEY_ENC_SECRET`；
3. 包源：`packages-src/` 作为内联资源或 KV，`env.PACKAGE_SOURCE_DIR` 指向；
4. `wrangler deploy`——入口 `src/index.js` 的 `export default { fetch }`。

## 纪律

- **零删除**：测试全部走 D1 内存 mock + `os.tmpdir()` 临时包源，不做任何文件删除。
- **共享链**：`withAuth/withCfMesh/withPath/withUsage/withAudit/withNativeGuard` 经 compose 装配，
  `run()` 在顶层建立 ALS 上下文、重入复用（与 tc-js-skeleton 同语义），跨类型互环不漏检。
- **三字段信封**：所有短路信封 `rst_types/rst_data/rst_err` 三字段，`run()` 原样透传不二次包裹。
