# 2026-05-09 — text-cli → MCP 桥设计日

> 待 Embedding-3 接入后摄入英雄碎片  
> 下午追加：密钥管理 + service 部署 碎片 9-14

---

## 碎片 1：文本指令的规范性定义

```
文本指令 = 文本 + 稳定语义空间投射 + 网络可分发
```

三个条件递进约束：
- **文本**：零 schema、零 migration、零版本号。牺牲编译期检查换零耦合
- **稳定语义空间投射**：semantic_id 是空间坐标（给机器），alias 是友好名（给人）。坐标不翻译
- **网络可分发**：区分于 shell 命令和本地脚本。指令自包含，不依赖本地上下文

这是规范性的——描述 text-cli 应该成为什么。

---

## 碎片 2：L0→L5 进化线

```
L0: eval(s_order[1])                         — 本地直接 eval
L1: order_config + host_service              — 查表→POST func_content
L2: /dsl_func/ + dsl_func_mapping           — 二级路由 + 函数组合
L3: /web_service_func/ + import 白名单       — eval + 计量 + 执行
L4: agent-copilot + semantic_registry        — Handler 注册 + 语义坐标
L5: L4 + MCP routing                          — mcporter call
```

每一步不推翻上一步，只换执行层实现。骨架从未改变：解析 → 路由 → 执行。

---

## 碎片 3：func_content 的消失——最关键的断裂

L0 到 L3，`func_content` 是统一脊柱——同一个 Python 字符串贯穿所有层：
```python
psot_data = {'type':'','data':{'func_content': 'basic_application_baidu_search(["威海天气"])'}}
```

但也携带 `eval` 的安全风险。L5 用结构化参数替代它：
- 失去：「一个字符串通吃所有层」的简洁
- 换来：「每一层都不需要信任上一层的代码」

这是安全模型从「信任下层」转向「零信任」的必经历程。

---

## 碎片 4：import 语句就是白名单

L3 的安全边界不在 `eval` 的输入过滤，在 `import`：
```python
from func.func_app.power_by_web_service import (
    execute_function_by_func_content,
    check_and_update_usage
    # ← 只 import 了 4 个函数
)
# eval 能调用的仅限于此，其他都是 NameError
```

MCP 的 `list_tools()` 完全同构。白名单的载体变了（Python import → JSON tool schema），但原理相同。

---

## 碎片 5：计量在执行之前，不在之后

L3 的 `check_and_update_usage` 模式：
```python
check_func = check_and_update_usage(func_name)  # ← 先检查配额
if check_func['rst_data'] == 'ok':
    rst_data = execute_function_by_func_content(...)  # ← 再执行
else:
    rst_data = '该指令所依赖的服务当前调用已达上限'
```

计量从一开始就嵌入执行层里。对 MCP 代理的启示：计量门控放在 mcporter call 之前，不是之后。

---

## 碎片 6：30 分钟冷启动 vs 4 小时 session

bge-m3 本地模型的实测数据：加载 30 分钟，session 4 小时。12.5% 的生命浪费。

> 「免费」也是有时间成本的。本地模型的「免费」不花 API 钱，但花的是 session 命。

结论：在线 Embedding-3 主力 + bge-m3 极端守卫（cosine < 0.7 才加载）。用 API 费换 session 命。

---

## 碎片 7：mcporter 不是客户端依赖

MCP 代理架构中 mcporter 的位置：
```
客户端 ──文本指令──▶ text-cli Endpoint ──mcporter──▶ MCP Server
```

客户端只发 HTTP POST，不需要 mcporter，甚至不需要知道 MCP 存在。mcporter 是 Endpoint 的内部依赖。

MCP 传输层就是 HTTP + JSON-RPC，不到 10 行代码可硬写。mcporter 是便利层，不是协议栈。

一个人和一个模型接入 text-cli 的最简形态：一个 URL + Schema 自描述 + 文本即协议。curl 一行搞定。

---

## 碎片 8：协议汇聚层

```
          ┌─────────────┐
文本指令 ─▶│  text-cli   │──▶ mcporter   ──▶ MCP Server A
          │  Endpoint   │──▶ HTTP fetch ──▶ MCP Server B
          │             │──▶ HTTP POST  ──▶ 传统后端 C
          └─────────────┘
```

Endpoint 向上提供统一接口，向下适配多种调用方式。公共端点就是 text-cli 的 DNS——调用方只需要一个 URL。

---

## 碎片 9：指令 domain 命名的自我约束

`文件`/`邮件`/`Git`/`密钥` — 全是具体的、自解释的名词。

`平台` 是反例——抽象、模糊、不像个名词。domain 名是语义空间的坐标，必须像地名一样直观：看到名就知道这片区域管什么。

action 不重复 domain 信息：`密钥;注册` 而非 `密钥;注册密钥`。domain 已经说了 密钥，action 只说动作。

---

## 碎片 10：密钥管理的双模态

密钥指令不是单一实现——是同一协议下的两种部署形态：

```
copilot (:20260) — 完整版
  密钥;注册 → XOR解密 → 加密落盘 → 审计日志
  handler 内部直接调 key_registry.get()
  
service (:8000) — template 可选装
  text-cli-modules/sqlite/ 目录存在 → 自动加载
  不存在 → 零数据库运行
```

指令格式完全相同——调用方不关心对面是 copilot 还是 service。协议统一，实现分层。

---

## 碎片 11：数据链验证 — 一封邮件验证四个系统

```
外部客户端 → service(:8000) → copilot(:20260) → SMTP
        公开端点            私域端点           外部服务
```

一封 `指令:邮件;发送,...` 同时验证：
- 模板部署（开源代码在独立目录运行）
- 职责分离（模板只路由，copilot 只执行）
- 密钥管理（SMTP 密码在 copilot，模板碰不到）
- 外部集成（开 8000 端口后任何客户端可调）

密钥管理指令本身也走同一条管线——`指令:密钥;注册,...` 经 service 转发到 copilot。没有特殊通道。

---

## 碎片 12：本地性的安全边界

bge-m3 的「慢」是天然保护——DDoS 打不死（排队等 GPU），盗刷无套利空间（不按调用计费）。

切到在线 Embedding-3 后，这层保护消失了——按 token 计费，盗刷直接烧钱。

安全模型必须补位：Service Token + 调用方额度 + 私域不对外暴露。本地模型的物理隔离 → 在线服务的身份鉴权。

---

## 碎片 13：text-cli-modules/ — 可选装模块的命名

`modules/` 太泛——任何 Python 项目都可能有个 modules/。`text-cli-modules/` 明确归属，不会撞名。

命名是产品设计的一部分。一个好的名字减少一次误解。

---

## 碎片 14：XOR 密钥永远不自己加密自己

密钥管理系统中 XOR_KEY 的分布：
- 预配置在 copilot 的环境变量（不参与网络传输）
- lemondy 手动持有同样的 XOR_KEY（本地加密用）
- 指令中传输的是 XOR 密文（不传输 XOR_KEY 本身）

> XOR_KEY 不自己加密自己。密钥管理的信任根不在网络里，在部署时手动注入的秘密里。
