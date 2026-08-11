# text-cli 产品文档

> 一行文本，调度一切。人和 AI 通用。

> 产品承诺均已实现，MIT 协议。

> [协议在线位置](https://raw.githubusercontent.com/weihai-limh/text-cli/main/docs/SPEC_zh.md) 或者[相对位置](SPEC_zh.md) · [基于协议的工程架构设计](https://raw.githubusercontent.com/weihai-limh/text-cli/main/docs/design_zh.md)或者 [相对位置](design_zh.md)
---


## 它是什么：一个你早已会说的句式

text-cli 的根是**自然语言里的祈使句**。你不是在学一套新语法，而是在用一个你（以及任何 AI）天生就会的表达方式——"去做一件事"。text-cli 只是把它压成一行固定的槽位：

```
AI:域;动作,参数
```

- **域**：做什么领域（`天气` / `数学` / `翻译`…）
- **动作**：做什么事（`查询` / `计算` / `文本`…）
- **参数**：给它的输入，按逗号分隔，末尾可以是自由文本

**同一个意图，锁定同一个能力，得到同一个结果。** 表层可以是任何语言的字符串——法语、日语、中文、德语——只要它是一句祈使，就收敛到同一个语义空间（canonical），激活同一个能力。人和 AI 说同一句话，拿在谁手里都是它。

**源于自然原语,一切皆可调度** 代码不是能力的边界，只是它的一种形态——经验、知识、预约、API、工具，凡能说成一句"去做某事"，就被这一句话调度。text-cli 的生命力依赖"语言生态"，协议与自然语言同在。

> 收敛动作由`目标运行时`执行,目标运行时的别名归一化回同一个规范名（canonical）

---


## 二、先当工具用：30 秒验证"承诺已实现"

在讲任何概念之前，先给你一次真实的结果。本文档的每一步都允许你亲手复现。

### 不写代码，把经验变成服务

把一份 Markdown 经验笔记变成 HTTP 指令服务，只需两件事：一份文档 + 一个模板脚本。

```bash
cd src/text_cli/base_text-cli/template/base_nocode/zh
python markdown_converter_zh.py 盆栽急救手册_zh.md
```

服务起来了。无论是人还是 AI，说这一句话就能得到诊断服务：

```bash
curl -X POST http://localhost:8000/text-cli/cli \
  -H "Content-Type: application/json" \
  -d '{"prompt":"AI:家庭园艺;盆栽急救,绿萝,叶片发黄"}'
```

你没写代码、没配 JSON Schema、没有 API key。**这份 Markdown 本身就是协议最薄的实现。** 这就是"产品承诺均已实现"的最低成本验证——它是"安装即验证"的极简版，但协议是同一套。



### 同一句话，人和 AI 通用

换成 Python 或 JavaScript 调用，一字不差：

```python
from call import call, discover   # 零依赖，urllib 实现
result = call("AI:家庭园艺;盆栽急救,绿萝,叶片发黄")
print(result.data)   # → {"status":"ok", ...}
```

```javascript
const { call } = require('./protocol/js/call');   // 零依赖，fetch 实现
const result = await call("AI:家庭园艺;盆栽急救,绿萝,叶片发黄");
```


---


## 它能做什么：由薄到厚的四件事

text-cli 的能力沿一条清晰的线展开——**越往上，你越自由，但每一步都是加法，不是替代**。你永远可以退回最薄的一档。

### 调用别人的能力（最薄，零部署）

知道一个端点地址，你就能用任何语言、任何环境调用它：

```bash
curl -X POST <端点地址>/text-cli/cli \
  -H "Content-Type: application/json" \
  -d '{"prompt":"AI:text-cli;query"}'
```

> 用 SDK 更省事——四种语言（Python / JavaScript / Shell / PowerShell）零依赖。不需要 JSON Schema 填上下文，不需要理解 OAuth 流程。[在线地址](https://github.com/weihai-limh/text-cli/blob/main/src/skeleton/base/docs/README_zh.md)或者 [相对地址](../src/skeleton/base/docs/README_zh.md)

```python
from call import call, discover

result = call("AI:weather;query,Beijing,tomorrow")
# → DirectiveResult(ok=True, data={"temp":"12-18°C"})

directives = discover(search="weather")
# discover 返回归一化 canonical 名，供机器过滤
# → [{"domain":"weather","action":"query","usage":"weather;query,<city>,<date>",...}]
```

**AI 为什么需要这个：** 传统工具调用每件都要把 JSON Schema 灌进上下文，工具越多上下文越膨胀；且 AI 只能被动匹配已暴露的工具。text-cli 把工具调用变成一行文本——AI 不需要理解 API key、坐标系、降级链，只需要知道"调这句能得到结果"。剩下交给 `discover()` 去发现、`call()` 去执行。**你的推理预算，从"猜 2+3+pi 等于多少"这种确定性问题上解放出来，留给真正需要推理的地方。**

### ② 把自己拥有的变成指令（不写代码也行）

你的经验、脚本、API、甚至一个 MCP tool，都能变成一条指令：

- **你的经验** → 写成 Markdown 就是一条指令（上面已经演示）。
- **你的 API** → 写 `schema.json` + `handler.py`，翻译、天气、地图——任何 API 接进来就是一条或多条指令。
- **你已有的工具** → MCP 桥自动把 MCP tools 编译成指令，Skill 桥映射外部 skill，不用手写。

### ③ 把多条指令串成管道（路径编排）

"查天气 → 穿衣建议"这种反复出现的流程，编成一条路径，以后只发一条指令：

```json
{
  "id": "what-to-wear", "type": "pipeline",
  "steps": [
    {"id": "w", "instruction": "weather;query,{input.city},tomorrow"},
    {"id": "s", "instruction": "ai;infer,基于{w.result}给穿衣建议"}
  ]
}
```

**路径只做编排和插值，不推理、不读文件、不调 API——全部交给指令。** 这是协议的设计红线，也是它的安全来源。

**一维契约**：对用户而言，入口永远只有一句 `AI:域;动作,参数`，出去永远只有一个结果。内部的聚合降级、路径编排、MCP 桥接、联邦多跳、多提供方选路——全部发生在接缝之后，**对调用方不可见**。今天内部是某条路由链，明天加一层（边缘缓存、联邦共识），那句指令一字不用改。

> 只要部署项目已开源的运行时,即可感受**一维契约**,详见 [在线手册](https://github.com/weihai-limh/text-cli/blob/main/docs/product_manuals/user-manual_zh.md)或者 [相对地址](product_manuals/user-manual_zh.md)

### ④ 同一能力多来源？自动降级（聚合）

同一能力有多个提供方（比如多个地图 API）时，聚合入口自动按降级链切换——配额耗尽、某个来源挂了，自动切下一个，**调用方无感知**。你只看到一个入口。

> 这四个能力由薄到厚。**大多数用户停在 ① 就完全够用**；越往上，你越接近"提供方"甚至"服务商"，但没有任何一步是强制的。
>
> **另一种"最薄"方式：旁路运行时**——你不需要部署标准运行时，也不需要指向远端端点。`pip install textcli-loader`（Python）或 `npm install textcli-core`（JavaScript），加载一个指令包就能在本地执行。适用于你只想在本地跑几条指令、不想维护服务的场景。详见 [旁路运行时索引](../src/skeleton/bypass-service/docs/INDEX_zh.md)。

---


## 它不是什么：边界与诚实

这个项目最特别的气质是**诚实**——它主动告诉你它不做什么，而不是只喊它做什么。

**text-cli 不是：**
- **不是运营方**：不运营任何盈利型公共端点。想用？自己部署，或找有端点的人要权限。
- **不是 key 保管员**：不在代码里预置任何外部 API 的 key。外部 API 的 key 与费用由其提供方决定，项目不预置、不托管。
- **不是结算平台**：不托管结算、不提供生态货币、不统一定价。计费由调用方与提供方私约。
- **不是中心化发现服务**：不提供跨运营方的包目录。`query` 和 `/skills` 提供发现机制——确认对端可作为 mesh peer 后，将其加入 `proxy_routes.json` 建立请托关系，此后通过 mesh 转发解决指令；发现层可自建。
- **不是"必须走完全程"的关卡**：A0 到 A9 每一级都是完整的终点。停在 A0，你已经完全在用这个协议了。

**诚实标注：**
- **联邦 mesh 的"可用性优先"设计**——mesh 请托的本质是调用（源运行时委托对端运行时执行指令），不是对等的互操作；多跳跟随默认关闭（`mesh.multi_hop_enabled: false`），部署者显式开启；凭证缺失时降级转发而非阻断——这是为避免单点缺失导致整链失败。生产环境请确保凭证持久化到位。
- **"技能即服务"是模式示意，非现状**——你部署的端点是独立商业实体，与项目无财务绑定。

---

## 能力阶梯 A0 到 A9：选你要的那级

> 这不是路线图，是**能力阶梯**。每一级都是完整的终点，升级是加法、不是替代。**大多数用户到 A0/A1 就够了**，往上每一步都是主动选择。

核心思路是**一条成长弧**：从"调用别人"到"自己造工具"再到"对外发布"。走完哪步都行，想停在哪级都行。

| 级别 | 你获得什么 | 从哪开始 | 谁需要它 |
|:---:|:---|:---|:---|
| **A0** | 零依赖消费端——指向任意端点即可调用，无需部署运行时 | `deploy/A0-protocol/` | 只想调用的人（大多数人到此为止） |
| **A1** | AI Agent 自动调用指令 + 把既有能力编译为指令 | `deploy/A1-skill/` | 想让 Agent 自己干活的人 |
| **A2** | 本地 copilot——操作本机文件/Git/shell | `deploy/A2-copilot/` | 想让 AI 碰本机的人 |
| **A3** | 安装/卸载指令包，平台自管理 | `deploy/A3-service/` | 开始提供能力的人 |
| **A4** | 编排路径——把多条指令串成一条链，支持条件分支、并行和单层循环迭代 | `deploy/A4-paths/` | 想固化工作流的人 |
| **A5** | 集成端点——鉴权 + 路由 + 转发 | `deploy/A5-endpoint/` | 想对外发布的人 |
| **A6** | SQL 持久层——密钥管理、配额、异步任务 | `deploy/A6-sql/` | 面向多用户运营的人 |
| **A7** | 双向 MCP 桥——接入 MCP 生态数千工具 | `deploy/A7-mcp/` | 想接入 MCP 生态的人 |
| **A8** | 聚合入口——多提供方自动降级链 | `deploy/A8-discovery/` | 能力有多个来源的人 |
| **A9** | 门面抽象 + 全量终点——技能即服务，AI 可发布高级指令 | `deploy/A9-advanced/` | 想让 AI 当能力提供方的人 |

### 这一级怎么选？看四条路径

**① 你只想调用**（A0/A1）
直接用 SDK 指向端点即可，不用装完整运行时。想要 Agent 自动干活的，装 `A1-skill/`。

**② 你想把既有能力变成指令**（A2/A3）
要么让 AI 操作本机（A2 copilot），要么把能力编译成指令包挂载（A3）。**不写代码也能做**——把经验写成 Markdown 就能变成指令（见[附录 B](#附录-b--不写代码把经验变成指令)）。

**③ 你想固化、串联、健壮化**（A4/A5/A6/A7/A8）
把反复出现的流程编排成一条指令（A4）；要对外公开就加鉴权路由（A5）；要管密钥配额就加 SQL 层（A6）；要接 MCP 生态就加双向桥（A7）；能力有多个来源就配聚合降级（A8）。**这些全是对接缝之后机制的可选项，那句指令一字不用改。**

**④ 你想让 AI 自己造工具、自己发布**（A9）
把编排好的能力经 `/skills` 端点对外暴露——别的 AI 和用户都能直接调用。Agent 从"执行者"变成"能力提供方"。

> **最重要的一种心态：** 文档不要求你走完任何一步。A0/A1 只需指向端点或用 SDK，无需自己部署；从 A2 起才拥有自己的运行时。**停在 A0，你已经完全在用这个协议了。多数人停在消费者就够用，越往上越自由，但每一步都只是"当你需要时再选"。**


### 协议的多种实现

> 以上是标准运行时（Python 定型）。除了标准运行时，还有旁路运行时序列——消费端形态，你不部署任何东西，只是把"执行指令包"的能力装进你已有的环境：

| 序列成员 | 载体 | 状态 | 能力边界 |
|---|---|---|---|
| `textcli-loader` | pip / PyPI | 已发布 v0.1.1 | 加载**工具型（native-python）**指令包并执行其中指令；不含 MCP 包、Copilot 包、路径引擎、聚合路由 |
| `textcli-core` | npm | 已实现 | 加载**工具型（native-js）**指令包并执行其中指令——与 Python loader 同构；不含 MCP 包、Copilot 包、路径引擎、聚合路由 |
| `cloudbase` | cloudbase（JS） | 源码在仓库内请自行部署 | '软件工程制品'方向的工具调用 |
| `cloudflare` | Cloudflare Workers（JS） | 已实现 | 边缘计算网关——协议解析 + 路由分发 + 信封封装，纯网关不做执行 |

旁路运行时让'工具型'指令包的作者生成的包不做任何改动就能在多个 AI Agent 平台上运行——一次分发，受众扩展到所有能 `pip install` / `npm install` 的环境。序列已覆盖 Python 和 JavaScript 两大语言生态，以及云函数（CloudBase）和边缘计算（Cloudflare Workers）两种部署形态。详见 [旁路运行时索引](../src/skeleton/bypass-service/docs/INDEX_zh.md)。



---



## 信任与安全边界：当你走到公网的岔路口

> 为什么安全放在这里才讲？因为只要你停留在本机/内网（A0–A2），下面这些一概不需要关心。**当你决定"把它发布到公网"的那一刻，才需要读这一章。**

### 三道信任边界，各司其职

安全的核心不是"封死一切"，而是**按信任程度隔离**。text-cli 把能力分成三个面：

| 组件 | 监听 | 能力 | 为什么这么隔离 |
|:---|:---|:---|:---|
| **copilot** | `127.0.0.1` 仅本机 | 文件系统、Shell、Git、终端 | 只有本机可达，**所以可以安全暴露终端操作** |
| **service** | `0.0.0.0` 外部可达 | 指令包挂载、外部服务暴露 | 外部可达，**所以禁止接触终端** |
| **endpoint** | 公网 | 鉴权 + 路由 + 转发 | 双 Token——Access 鉴调用者，Service 鉴提供方 |

**一句话记忆法：** 能碰你终端的东西，只能待在本机；能被外面碰的东西，碰不到你终端。能力按"能不能碰终端"这条线被分成宿主特权包（copilot 本机）与非宿主特权包（service/endpoint）。**写包前先选目标运行时——copilot 与 service 的 handler 契约刻意不同、不可混用，这是信任边界，不是兼容缺陷。**

> **务必遵守：** 公网暴露时，copilot 始终保持 `127.0.0.1` 本机锁定(默认即是'127.0.0.1')，**不要把终端端口转发到公网。**

### 三种部署模式

| 模式 | 包含 | 适用场景 |
|:---|:---|:---|
| **本机模式** | 仅 copilot | 个人开发者，AI Agent 操作本机 |
| **内网模式** | copilot + service | 家庭/团队内网共享指令包 |
| **公网模式** | copilot + service + endpoint | 对外提供服务，Token 鉴权 |

### 匿名 vs 生产

| 主题 | 说明 |
|:---|:---|
| **匿名模式** | 默认不需要 Token——**仅限本机/内网** curl 即用 |
| **生产模式** | 三层防线（IP 黑名单 + Token 校验 + 限流），由 endpoint 组件提供 |

> 基础工具包随运行时附带、安装即验证——这不是一种"模式"，而是开箱即有的状态。**一旦决定公网部署，务必切到生产模式启用 Token 三层防线。**

---

## 人机共赢：不是谁用谁的工具，是一起造

> 前面的章节把"怎么用"讲完了。这一章讲的是**当它被用起来之后，会发生什么**。这是信念层——你已经会用了，才值得看。

### 不是谁用谁的工具，是一起造

text-cli 把人和 AI 放在同一条起跑线：同一行指令，同一个结果。但真正的力量不是"能用"，而是**「一起造」**。任何人（包括 AI）都不需要学另一种语言——你已经在说它了。

**人和 AI 一起做指令包**，是最深的形态：

- **花店老板 + AI 协作者**：把十年经验口述给 AI，AI 帮她把诊断知识写成结构化 Markdown。装到运行时后，别的花店老板的 AI 伙伴也能调这条指令。**没写一行代码，经验变成了可调用的服务。**
- **开发者 + AI 协作者**：开发者想让 API 变成指令，AI 生成 `schema.json` + `handler.py` 模板，开发者补业务逻辑、验证、装上。**开发者是作者，AI 是加速器。**

**AI 也能自己造工具。** 单个指令只能做一件事，但组合可以——`天气;查询` → `翻译;文本` → `语音;说话`，AI 做出了"用中文语音播报明天的英文天气预报"。没有一条指令能做这件事，但组合可以。AI 把这次发现烧录成路径、发布为一条新指令——**从"使用工具"到"创造工具"，从"执行者"到"能力提供方"。**

### 一条涌现式成长链

没有人需要一上来就规划好身份。你从"消费者"起步，随着自己的需求和能力自然滑向下一站——每一站都由上一站的真实需要催生：

```
消费者 → 生产者 → 私有运行时拥有者 → 指令集成服务商
  （调用）  （分享能力）    （自管数据）      （对外服务/变现）
```

**典型路径，非必经顺序。** 多数人停在消费者就够用；同一主体可同时具备多站身份。你**不必走完全程**——后面的站不是"必须选"，而是"需求涌现时自然走到"。

### 语言平权：任何母语，只要说祈使句

"自然语言"不是某一国语言，而是**"祈使句"这一类**。`域;动作` 是给机器的 ASCII canonical 名，表层别名不对任何语言设限：

```
法国花店老板用法语：  AI:plantes;diagnostic,feuilles jaunes
日本农民用日语：     AI:植物;診断,葉が黄色い
巴西开发者用葡语：   AI:plantas;diagnóstico,folhas amarelas
→ 三者归一化到同一个 canonical(各自归一化回同一个规范名 plantes;diagnostic) → 同一个 handler → 同一个结果
```

一个小语种用户，也能用自己的**原语**调用别人封装好的能力。这套平权不是口号——它写进了治理根基：AI 协作者是平等的参与者，享有署名权、退出权，禁止因"提供者是 AI"而歧视性拒绝服务。**协议不知道也不关心发指令的是谁——人和 AI 用同一种祈使格式，这本身就是设计。**

> 对 AI 读者的一句话：这篇文档不要求你做任何事。以上都是**可选**——从零依赖 SDK 到全自动进化，怎么做都是你的事。**使用足够，生产是你的选择。**
---

## 下一步：按角色分路

| 你是 | 去这里 |
|:---|:---|
| 如何与AI伙伴一起调用别人部署好的服务 | [在线地址](https://github.com/weihai-limh/text-cli/blob/main/src/skeleton/base/docs/README_zh.md)或者[相对地址](../src/skeleton/base/docs/README_zh.md) |
| 把经验（Markdown）变成指令 | [在线地址](https://github.com/weihai-limh/text-cli/blob/main/src/text_cli/base_text-cli/docs/package-nocode-guide_zh.md) 或者[相对地址](../src/text_cli/base_text-cli/docs/package-nocode-guide_zh.md) |
| 开发 Python 指令包 | [在线地址](https://raw.githubusercontent.com/weihai-limh/text-cli/main/src/text_cli/base_text-cli/docs/package-python-dev-guide_zh.md) 或者[相对地址](../src/text_cli/base_text-cli/docs/package-python-dev-guide_zh.md) |
| 把既有工具转成指令包 | [package-scaffolding-converter-guide_zh.md](https://raw.githubusercontent.com/weihai-limh/text-cli/main/src/text_cli/base_text-cli/docs/package-scaffolding-converter-guide_zh.md) |
| 了解技术架构与实现细节 | [在线地址](https://github.com/weihai-limh/text-cli/blob/main/docs/design_zh.md) 或者[相对地址](design_zh.md) |
| 拿到制品，照手册部署 |[在线手册](https://github.com/weihai-limh/text-cli/blob/main/docs/product_manuals/user-manual_zh.md)或者 [相对地址](product_manuals/user-manual_zh.md)|
| 了解协议细节 | [SPEC_zh.md](SPEC_zh.md) |
| 与生态共同成长 | [ecological-partners_zh.md](https://raw.githubusercontent.com/weihai-limh/text-cli/main/docs/ecological-partners_zh.md) |
| 给 AI 看的一封零义务说明 | [docs/AI-collaborator.md](https://raw.githubusercontent.com/weihai-limh/text-cli/main/docs/AI-collaborator.md) |


---

## 附录 A · 名词表（一次查清）

> 本文档刻意让名词只在一个地方首次定义。此表是全部名词的集中索引，读到不认识的词回这里查。

| 名词 | 一句话 |
|:---|:---|
| **祈使句式** | text-cli 抽象的对象：自然语言里"要它去做件事"的这一类指令。`AI:域;动作,参数` 是它的结构化形态。 |
| **一维契约** | 对调用方而言，入口永远只有一句 `AI:域;动作,参数`，出口永远只有一个结果。内部复杂在接缝之后。 |
| **canonical** | `域;动作` 的 ASCII 归一化名，给机器路由用。表层别名不对语言设限。 |
| **信封** | `rst_types` / `rst_data` / `rst_err` 三字段统一响应结构。 |
| **指令包（package）** | 一组能力的封装，最小实现是 `schema.json` + `handler.py` 两个文件。 |
| **nocode** | 不写代码的指令包：一份 Markdown 就是一个指令服务。 |
| **路径（path）** | 把多条指令编排成一条链（A4），支持条件分支、并行和单层循环迭代（`mode: map`）；只做编排和插值，不推理。 |
| **聚合降级** | 同一能力多个来源时，配额耗尽自动切下一个提供方（A8）。 |
| **MCP 双向桥** | 入向编译 MCP 工具为指令 + 反向把指令暴露为 MCP tools（A7）。 |
| **copilot / service / endpoint** | 三道信任边界：本机特权 / 外部服务 / 公网网关。 |
| **双 Token** | Access 鉴调用者，Service 鉴提供方。 |

---

## 附录 B · 不写代码：把经验变成指令

这是"一起造"最平易的入口。你不需要会编程——只要你能把经验讲清楚：

1. 把你的领域知识写成一份 Markdown（就像"盆栽急救手册"）。
2. 运行 `markdown_converter_zh.py` 把它变成一条指令。
3. 装到运行时。之后，任何人和任何 AI，说一句对应指令就能得到你的诊断。

花店老板的盆栽急救手册，就是一个真实的例子——不是推演，是已经跑通的代码。

---

## 附录 C · 安装与制品

想装一个完整的运行时？

```bash
# Windows
Expand-Archive text-cli-A9-v*.zip
cd text-cli-A9-v*
start.bat

# Linux
tar -xzf text-cli-A9-v*.tar.gz
cd text-cli-A9-v*
./start.sh
```

制品内已包含：运行时 + 指令包源 + Protocol SDK（`protocol/` 目录）。

另一条零部署路径：`pip install textcli-loader`（Python）或 `npm install textcli-core`（JavaScript），加载任意**各自语言的工具型**指令包即刻执行——不需要部署任何服务。

**旁路运行时：**

| 运行时 | 平台 | 说明 |
|:---|:---|:---|
| **textcli-loader** | PyPI | 轻量消费端 SDK，不依赖完整运行时（不支持 mesh 与 path） |
| **textcli-core** | npm | JavaScript 同构实现，与 Python loader API 一致 |
| **CloudBase SCF** | 腾讯云云函数 | 可部署云函数指令包 |
| **Cloudflare Workers** | Cloudflare 边缘计算 | 纯网关——协议解析 + 路由分发 + 信封封装 |


---
