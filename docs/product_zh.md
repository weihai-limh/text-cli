# text-cli 产品文档

> 分布式指令分发骨架：把一台机器上的服务和工具变成文本指令。你 curl 发一行，它出结果。AI 也发同一行。
> **版本**：v0.1.1 | **日期**：2026-07-23 | **配套文档**：`SPEC_zh.md`

---

## 一、你被什么困扰

AI 需要使用工具——只用推理解决不了计算、查天气、搜地图这类需要确定性的机械任务。

但现在调用工具的方式太重：每件工具都要占用上下文去读它的 JSON Schema、理解参数语义。工具越多，上下文越膨胀。更糟的是，AI 发现工具的能力是被动式的——只能匹配上下文中已暴露的工具。一个端点还有什么工具可以用，不提前告诉 AI 就不知道。

**AI 需要工具，但调用太重、发现太被动。**

---

## 二、text-cli 解决什么

text-cli 是**分布式能力分发系统**。部署到一台机器后，这台机器上的服务和工具作为"能力源"对外提供能力。

任何人都能写指令包装到骨架上。任何 Web 在线服务（API、MCP、脚本）接进来就是一条或多条指令。在协议层，无论你是人、是 AI、在 webchat 里还是在 agent 里——同一个请求，同一个响应。

**text-cli 和 MCP 是不同层的协议，不竞争。** MCP 是工具暴露协议——"有什么工具可以用"。text-cli 是工具调度协议——"谁来执行、怎么降级、如何计费"。MCP 生态的工具通过 A7 双向桥灌入 text-cli，与其他来源（指令包、API、nocode）在降级链中地位平等。同样，text-cli 的指令也可反向暴露为 MCP tools，被标准 MCP 客户端直接调用。

**人和 AI 共用同一个遥控器。** 人发 `AI:天气;查询,明天,威海`，AI 也发同样的指令。自然语言是两端——人用自然语言表达意图，AI 用自然语言呈现结果——中间是精确的管道路径。

### 加工链

```
    文本 ──→ 指令分发 ──→ 聚合降级 ──→ 增值结果
                         路径编排
                         异步委托 (--async)
                         联邦 mesh 多跳
                         知识萃取
                         配额保护
```

### 同一个 Agent，不同阶段不同用法

**A1 — 调用技能。** Agent 匹配到指令后，组装文本发送 HTTP 请求。不必理解 API key、坐标系、降级链——只需要知道"调这个指令能得到结果"。

```
用户说"明天威海穿什么？"
→ Agent 查指令库 → 天气;查询,明天,威海
→ curl → 返回: {"温度":"12-18°C","天气":"晴"}
```

**A2 — 代理本地终端和 Skill。** Agent 需要操作本地文件、执行 shell 命令。通过 copilot 的 terminal 代理，这些操作被封装为 text-cli 指令——每一步可审计、可限权。同时通过 Skill Bridge 调用技能市场的 skill，协议层桥接不同工具来源。

**A3 — 安装指令包。** Agent 发现请求需要翻译能力，但当前服务没有。它安装翻译指令包：`AI:text-cli;install,xx-cloud` → 新能力上线。不修改代码，不重启进程——指令包是自包含的能力单元。**标准运行时已附带 10 个核心工具包**（JSON/Markdown/数学/日期/SQL/表格/归档等），安装即验证。

**A4 — 编排路径。** Agent 发现"查天气→穿衣建议"的组合反复出现。它把链条发布为路径：

```json
{"steps": [
  {"id":"w","instruction":"weather;query,{input}"},
  {"id":"d","instruction":"ai;infer,根据{w.temp}和{w.weather}给出穿衣建议"}
]}
```

`text-cli;pro` 之后，AI 只需要匹配 `穿衣;建议,威海`——路径编排对调用方完全透明。

**A7 — 映射 MCP 生态。** MCP 生态有成百上千个工具。Agent 不需要逐一对接——MCP 桥一次配置，MCP server 的工具自动编译为 text-cli 指令。Agent 用同样的 `AI:域;动作,参数` 协议调用，不感知底层传输差异。反向同样成立：text-cli 的指令也可经 A7 暴露为 MCP tools，让标准 MCP 客户端直接调用——桥是双向的，不是单向适配器。

**A8 — 聚合指令：一个入口，多源调度。** 地理编码可以引用多种源——有的来自指令包、有的通过 Skill 映射、有的通过 MCP 映射。Agent 只调 `map;geocode`——聚合指令内部按降级链依次尝试，配额耗尽自动切换，输出格式始终一致。

**A9 — 发布高级指令。** Agent 不只是调用者。它把编排好的能力发布为技能：`AI:text-cli;pro,地图连线`。注册后通过 `/skill` 端点暴露，其他 AI 和用户都能调用——Agent 从"执行者"变成了"技能提供方"。

### 两根脊梁：分布式 + 渐进式

| | 分布式 | 渐进式 |
|---|---|---|
| 什么意思 | 多台机器各自部署，各自暴露不同能力。换 IP 就是换能力源，调用方式不变 | 每级都是完整终点。升级是加法，不是替代 |
| 怎么体现 | `AI:text-cli;query` 在 A 机器返回翻译能力，B 机器返回地图能力——同一行指令，不同能力 | A0 curl 他人端点 → A3 自管平台 → A6 小企业工具 → A9 全量聚合 |
| 对谁重要 | 家庭多机器、团队多节点、公网多 service 聚合 | 从花店老板到开发者的全谱系用户 |

### 愿景

人和 AI 共用同一个遥控器。人发 `AI:天气;查询,明天,威海`，AI 也发同样的指令——不是"AI 用 API"和"人用界面"，是同一把遥控器，拿在谁手里都是它。

让每个人把经验变成指令，每台机器暴露出能力，每个 AI 用同一行指令调度世界。

---

## 三、渐进式部署——A0 到 A9

每一级都是完整的终点。升级是加法，不是替代。

### 标准运行时

| 级别 | 你能做什么 | 从哪开始 |
|:---|:---|:---|
| **A0** | 使用他人提供的 text-cli 服务——你只需要 curl | `deploy/A0-protocol` |
| **A1** | AI Agent 自动调用指令 + 将既有能力编译为指令 | `deploy/A1-skill/` |
| **A2** | 部署本地 copilot，操作本机文件/Git/shell | `deploy/A2-copilot/` |
| **A3** | 安装/卸载指令包，平台自管理。附带基础工具包可直接验证 | `deploy/A3-service/` |
| **A4** | 编排路径，串联多条指令成链 | `deploy/A4-paths/` |
| **A5** | 部署集成端点，鉴权+路由+转发 | `deploy/A5-endpoint/` |
| **A6** | SQL 持久层——密钥管理、配额追踪、异步任务 | `deploy/A6-sql/` |
| **A7** | 双向 MCP 桥（入向编译 + 反向暴露），成千上万工具 | `deploy/A7-mcp/` |
| **A8** | 指令发现与聚合入口，联邦 mesh 多跳 | `deploy/A8-discovery/` |
| **A9** | 聚合降级 + 多源统一 + 技能即服务 | `deploy/A9-advanced/` |

> A0/A1 只需他人端点，无需部署。A2 起拥有自己的运行时。A3-A9 是 service 的累积层级。完整导航见 `deploy/INDEX_zh.md`。

### 旁路运行时

除了标准运行时（Python），协议还支持其他运行时载体：

| 运行时 | 平台 | 说明 |
|:---|:---|:---|
| **CloudBase SCF** | 腾讯云云函数 | 指令包部署为云函数，经独立网关转发——不走标准 install 管线 |
| **textcli-loader** | PyPI（`pip install textcli-loader`） | 轻量消费端 SDK——在任何 Python 环境加载指令包并执行，不依赖完整运行时 |
| **Cloudflare** | 预留 | 待扩展 |

---

## 四、你获得什么能力

### 三种指令来源

| 来源 | 说明 |
|------|------|
| **安装的指令包** | 四种格式——native（代码实现）、nocode（经验服务化，零代码）、aggregate（纯声明降级链）、path（步骤链） |
| **MCP 生态** | 双向桥：MCP server 工具自动编译为 text-cli 指令；text-cli 指令也反向暴露为 MCP tools，供任意 MCP 客户端调用 |
| **copilot 代理** | 本机文件/Git/shell/终端——copilot 暴露后通过协议层调度 |

所有来源在降级链中地位平等——调用方不关心一条指令来自哪里。

> 💡 如果你有 Postman Collection、结构化 Markdown 或 MCP server，可以用 `converter/` 下的脚本快速生成指令包**脚手架**，再参考开发指南补全。详见 [`src/text_cli/base_text-cli/converter/`](../src/text_cli/base_text-cli/converter/)。

### 核心能力

- **路径编排**：多条指令串联成链。管道闭包原则——路径只做编排和插值，文件 IO、API 调用、推理全部通过指令
- **异步委托**：长任务加 `--async` 不阻塞，通过 `GET /text-cli/tasks/{id}` 查询结果——synth-loop 相位管道的执行基座
- **分布式分发**：多台机器各自部署，不同端点暴露不同能力。换 IP 就是换能力源，调用方式不变
- **联邦 mesh**：多节点互发现——非单层 hub-spoke 拓扑，节点间按 peer 凭证注入、多跳转发、防环超时
- **聚合降级**：同一类能力有多个提供方时自动切换——配额耗尽 → 下一个顶上。调用方不感知
- **nocode 路径**：花店老板把十年经验写成 Markdown，不写一行代码，变成可调用的诊断服务

### 标准运行时附带的基础工具包

安装标准运行时后，以下指令包立即可用：

| 类别 | 指令包 | 能力 |
|------|--------|------|
| 数据 | `tc-json`、`tc-table`、`tc-sql` | JSON 解析、表格处理、SQL 查询 |
| 文本 | `tc-markdown`、`tc-diff`、`path-str` | Markdown 读写、差异对比、字符串模板 |
| 计算 | `tc-math`、`tc-datetime` | 表达式求值、日期计算 |
| 文件 | `tc-archive`、`image` | 归档压缩、图片转换缩放 |

> 这些包零或极轻依赖，安装即验证运行时完整性。

### 三种部署模式

| 模式 | 包含 | 适用场景 |
|------|------|---------|
| **本机模式** | 仅 copilot | 个人开发者，AI Agent 操作本机 |
| **内网模式** | copilot + service | 家庭/团队内网共享指令包 |
| **公网模式** | copilot + service + endpoint | 对外提供服务，Token 鉴权 |

### 三把能力的钥匙

| 钥匙 | 能力 | 安全边界 |
|:---|:---|:---|
| copilot（127.0.0.1） | 文件系统、shell、Git、终端 | 仅本机可达——所以可以安全暴露终端操作 |
| service（0.0.0.0） | 指令包挂载、外部服务暴露 | 外部可达——禁止接触终端 |
| endpoint（公网） | 鉴权+路由+转发 | 双 Token 模型——Access 鉴调用者，Service 鉴提供方 |

---

## 五、开始用

### 30 秒体验（无需部署运行时）

```bash
# 下载模板脚本，跑起来就能 curl
python markdown_converter.py 盆栽急救手册.md

curl -X POST http://localhost:8000/text-cli/cli \
  -H "Content-Type: application/json" \
  -d '{"prompt":"AI:家庭园艺;盆栽急救,绿萝,叶片发黄"}'
```

这是 text-cli 协议的完整缩影——不依赖框架，纯 Python 标准库。

### 部署标准运行时

```bash
git clone https://github.com/weihai-limh/text-cli.git
cd text-cli/deploy/A3-service
python main.py
```

```bash
# 验证
curl -X POST http://localhost:28050/text-cli/cli \
  -H "Content-Type: application/json" \
  -d '{"prompt":"AI:text-cli;query"}'
# → 返回所有可用指令（含已附带的基础工具包）
```

### 预设

| 主题 | 说明 |
|------|------|
| **开箱即用** | 基础工具包随运行时附带，安装即验证 |
| **匿名模式** | 默认不需要 token——内网 curl 即用 |
| **生产模式** | 三层防线（IP 黑名单 + Token 校验 + 限流） |

---

## 六、下一步

| 你是 | 去这里 |
|------|------|
| 先用起来，调几个指令试试 | 向上翻到 [30 秒体验](#30-秒体验无需部署运行时) |
| 调用别人部署好的 text-cli 服务 | `src/skeleton/base/docs/README_zh.md` |
| 把经验（Markdown）变成可调用的指令 | `src/text_cli/base_text-cli/docs/package-nocode-guide_zh.md` |
| 开发标准指令包（Python/API/容器） | `src/text_cli/base_text-cli/docs/package-dev-guide_zh.md` |
| 把既有工具快速转成指令包 | `src/text_cli/base_text-cli/converter/` |
| 部署自己的运行时 | `deploy/INDEX_zh.md` |
| 运营端点对外提供服务 | `docs/ecological-partners_zh.md` |
| 了解协议细节 | `docs/SPEC_zh.md` |
