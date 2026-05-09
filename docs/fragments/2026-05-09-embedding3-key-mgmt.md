# 2026-05-09 Session 英雄碎片

> 蒸馏自 embedding-3 接入 + 密钥管理实施 session
> 作者: Tide 🌊
> 日期: 2026-05-09
> 待摄入到 hero-fragments

---

## #1 密钥管理三层安全模型

**领域**: 安全架构
**标签**: 密钥管理, XOR加密, 本地加密, 审计

### 核心设计

密钥从注册到存储经过三层安全处理：

1. **XOR 传输加密**: 调用方用 `XOR_KEY_{service}` 加密明文 → hex 密文传输。网络链路上从未出现过明文。
2. **本地二次加密**: copilot 解密后，用 `KEY_REGISTRY_SECRET` 再次加密后才写入磁盘。`key_registry.json` 里只有 `encrypted_value`，没有 `plain_value`。
3. **审计日志**: 每次 KEY_REGISTER/KEY_REVOKE 写入 `call_log.jsonl`，记录时间+服务名+操作类型，不记录密钥值。

### 关键约束

- XOR_KEY 永远不自己加密自己——信任根在部署时手动注入的秘密里
- 环境变量名不能含连字符——bash 限制。用下划线替代，代码中做映射
- 列表接口只返回服务名+类型+时间，不返回密钥值
- 重复注册拒绝（需先撤销），避免覆盖攻击

### 数据链

```
curl → service(:8000) → proxy handler → copilot(:20260) → XOR解密 → 本地加密 → key_registry.json + call_log.jsonl
```

一条指令走完四层。

---

## #2 Service 代理转发模式

**领域**: 架构模式
**标签**: service, proxy, 数据链, 指令路由

### 模式

Service 作为协议汇聚层：收到指令后优先检查 `proxy_routes.json`，匹配则转发到下游（copilot），不匹配则本地处理。

```json
{
  "密钥;注册": {
    "url": "http://localhost:20260/cli/text_cli",
    "token": "...",
    "sensitive": true
  }
}
```

### 关键设计点

- Proxy 优先级高于本地 dispatch——先查代理表，再走本地
- `sensitive: true` 的指令在日志中省略请求体
- 代理是透明转发：service 不解析业务语义，只做路由
- 这正好验证了 §9 路径规范中的"编排模式"——service 作为枢纽

---

## #3 Embedding-3 迁移实操

**领域**: 工程实践
**标签**: embedding, API迁移, Worker部署, 语义注册表

### 迁移步骤

1. 语义注册表 13 条目批量调用 Embedding-3 API，全部生成 512 维向量
2. bgem3 Worker 源码切换为双引擎（embedding-3 主力 + bge-m3 守卫）
3. wrangler secret put BIGMODEL_API_KEY → wrangler deploy
4. 上线后验证：health 显示 primary=bigmodel/embedding-3，语义编码返回 512 维

### 经验

- Embedding-3 支持 4 种维度：A=256, B=512, C=1024, D=2048，一次 API 调用切换
- 四种模式全通，延迟 ~200ms，远优于 bge-m3 的 30 分钟冷启动
- 注册表迁移需要在 description 字段编码足够语义信息（取英文部分），否则向量锚点不准
- 旧注册表 (`_bge-m3.json`) 保留作为守卫参照锚点

---

## #4 wrangler 双认证模式

**领域**: 工具链
**标签**: Cloudflare, wrangler, 部署

### 发现

wrangler 支持两种认证：

1. **API Token** (`CLOUDFLARE_API_TOKEN`): 自定义权限令牌，推荐但需在 Dashboard 创建
2. **Global API Key + Email** (`CLOUDFLARE_API_KEY` + `CLOUDFLARE_EMAIL`): 全局密钥，直接可用但权限过大

之前只用 Token 方式失败了（Global Key 不是 Token），加入 Email 变量后立即通过。

```bash
export CLOUDFLARE_API_KEY="cfk_..."
export CLOUDFLARE_EMAIL="tide@10000.world"
export CLOUDFLARE_ACCOUNT_ID="82ed8ca..."
wrangler whoami  # 验证
```

---

## #5 enabled: false — 优雅禁用模式

**领域**: 工程实践
**标签**: 安全, 配置管理, 指令禁用

### 场景

`AI协作;消息` 的 push 模式可以写入任意 JSON 到文件。在有 API key 信息流动的 session 中，存在泄露风险。

### 方案

不删代码，不删配置，只在 `auxiliary_config.json` 中加 `"enabled": false`：

```json
"AI协作;消息": {
  "enabled": false,
  "_comment": "2026-05-09 暂时禁用 — push 模式可写任意 JSON",
  ...
}
```

三处代码适配：
1. `_register_handlers`: 跳过 `enabled === false` 的项
2. `_build_schema`: Schema 端点过滤禁用项
3. `dispatch`: 对禁用指令返回明确的 `disabled` 错误（非 `unknown_instruction`）

好处：代码完整保留，一行配置即可恢复。

---

## #6 检查点驱动的实施方法论

**领域**: 协作方法论
**标签**: 检查点, 清单, 实施节奏

### 本 session 验证

从 `embedding-3-checklist_0509.md` v2.0 出发，逐条执行：
- 先基础设施 → 再核心逻辑 → 再链路验证 → 再部署
- 每个阶段完成立即用 curl 验证，不攒到最后
- 阻塞项（CF Token）及时发现并解决，不拖慢整体进度
- 30 分钟产出：17/22 完成，核心链路全部贯通

检查点不只是"做到哪了"——它阻止了两次可能的错误方向（XOR_KEY 连字符、dispatch 逻辑顺序），每次纠正成本 < 2 分钟。

---

## #7 bash 连字符陷阱

**领域**: 运维
**标签**: bash, 环境变量, 命名规范

### 问题

环境变量名不能含连字符。`XOR_KEY_bigmodel-embedding-3` 在 bash 中非法。

### 解决

- 环境变量用下划线：`XOR_KEY_bigmodel_embedding_3`
- 代码中做映射：`f'XOR_KEY_{service_name.replace("-", "_")}'`
- `.env.keys` 文件同时记录两种命名对应关系

### 教训

跨语言系统的命名约定要在设计阶段对齐——Python 接受连字符的 dict key，bash 不接受。等运行时才发现，浪费了两次启动尝试。
