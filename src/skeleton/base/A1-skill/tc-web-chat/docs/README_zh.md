# tc-web-chat 

## 快速启动（3 步）

1. **打开**：双击 `tc-web-chat.html`（或托管到静态服务器，同源打开 `http://127.0.0.1:8000/`）。
2. **配后端**：点右上角 ⚙️，填入聊天后端 Base URL（如 `http://127.0.0.1:8000/v1/chat/completions`）和必要的请求头（API Key 走这里）。
3. **（可选）启 tc**：在 ⚙️ 面板「tc 指令消费」分组勾选 `tc_enabled`，填 `tc_endpoint`（本机默认 `http://127.0.0.1:28050/text-cli/cli`，需先起 text-cli 运行时）；在头部 `Tool Gate` 下拉选人闸档位。然后在输入框打字，`Enter` 发送；点 📎 上传多模态文件，点 `Language`/`Tool Gate` 切换语言与人闸，点 `Clean` 清屏重来。

> 想立刻体验？先起 text-cli 参考运行时（如 `zh/markdown_converter_zh.py` 监听 8000 端口，或 text-cli Service `:28050`），把 `tc_endpoint` 指向它，再启用 `tc_enabled` 即可让 LLM 在对话中调用指令。

---

## 目录结构

```
tc-web-chat/
├── tc-web-chat.html          # ★ both 版制品（内嵌中英双语，可运行时下拉切换）
├── tc-web-chat_zh.html       # ★ 单 zh 版制品（纯中文，单语隐藏语言下拉）
├── tc-web-chat_en.html       # ★ 单 en 版制品（纯英文，单语隐藏语言下拉）
├── tc-web-chat-src/          # ★ 源文件（进版本库，不进分发制品；多语言改造前为 dev/）
│   ├── build.js              # node 零依赖拼接脚本，--lang 支持 both/zh/en → 三件套
│   ├── i18n.json             # 唯一多语言源（en/zh 字典 + 注册表，构建注入）
│   ├── shell.html            # 外壳真源（DOM + CSS）
│   ├── tc-config.js          # 配置状态 + 消费注入的 LANGS/I18N + SYSTEM_PROMPTS
│   ├── tc-cache.js           # tcCache + tcDiscover() + tcQuery() filter
│   ├── tc-parser.js          # parseDirectives()（移植 parser.js）
│   ├── tc-approval.js        # 人审卡片 + 状态机 + 人闸下拉
│   ├── tc-quiet.js           # 免打扰轮编排闭包
│   ├── tc-chat.js            # 会话历史 / 渲染 / submit / Clean
│   ├── tc-integrate.js       # 唯一胶水层（按序内联进制品 <script>）
│   └── regression-checklist_zh.md # R5'–R9' 回归清单（防回归基线）
├── docs/README_zh.md              # 本文档（概述 + 契约状态）
├── docs/user-manual_zh.md         # 用户手册
```

> **源与制品纪律**：`tc-web-chat-src/` 是源（进版本库），三个 html（`tc-web-chat.html` / `_zh.html` / `_en.html`）是制品（分发交付物），由 `node tc-web-chat-src/build.js` 零依赖拼接生成。制品可由源重建；仓库丢 html 可重建，丢 `tc-web-chat-src/` 才真丢。分发时只发需要的 html（双语 `tc-web-chat.html` 或单语 `_zh.html`/`_en.html`）。构建自洽：外壳（DOM+CSS）收编为版本库真源 `shell.html`，`build.js` 读它注入源模块 + i18n 生成制品，不再依赖任何外部冻结件。多语言源唯一收敛于 `i18n.json`，加语言 = 改 `i18n.json` 一行，产物由 `--lang` 分发。

---

## 终端契约实现状态

依据 `tc-integration-design_zh.md` 的桥接契约：

| 契约层 | 状态 | 说明 |
|---|---|---|
| ① 聊天主链路 | ✅ 已实现 | OpenAI 兼容 `/v1/chat/completions`，SSE 流式优先 + 非流式降级（沿用旧版能力） |
| ② tc 指令消费 | ✅ 已实现 | `tc_enabled` 默认关；启用后拉取指令表单入浏览器缓存、免打扰轮执行 `AI:域;动作,参数`、双令牌头、`rst_err===''` 信封铁律、6 错误码闭集、降级非终态、`delegated`/异步 `task;status` 轮询 |
| ③ 人闸（安全闸） | ✅ 已实现 | `auto_execute` 三档（readonly/none/all）+ 头部 `Tool Gate` 下拉；人审卡字节同一性；CircuitBreaker 连续 3 次失败转 none |
| ④ 语言下拉化 | ✅ 已实现 | `LANGS` 注册表驱动头部 `Language` 下拉（替换旧 EN/CN 双按钮），加语言=加一行 |
| ⑤ 资源画廊 | ✅ 已实现 | `<resources>` 协议，图片/视频/音频/PDF/网页内联渲染；tc 的 `rst_types` 多模态复用同一画廊 |

**向后兼容**：`tc_enabled=false`（默认）时行为与旧纯聊天版完全一致；tc 能力为可选配置项，不填则不启用，不改双击即开体验。

**不实现项**：
- path 可视化编辑器：初版仅支持「文本注册 + 自动进发现」（path 经 `--register` 自动进 query，前端把 path id 当普通指令交给 LLM）。
- CORS / `file://` 双击场景：属聊天后端范畴，由 user-manual §5 故障排查体系负责，本终端不单独处理。

---

## 实测状态（端到端）

已完成对参考运行时的端到端实测（详见 `tc-web-chat-plan_zh.md`）：
- **发现链路**：`tcDiscover`（POST `{ep}` + `{"prompt":"AI:text-cli;query,json"}`）成功拉取指令表单，兼容 `rst_data` 包裹与数组两种形态。
- **执行链路**：`AI:域;动作,参数` 经双令牌头执行，回填 `rst_data`；`rst_err===''` 正确判成功。
- **鉴权闭环**：`SERVICE_DENIED` 正确映射（Service Token 无效），`ACCESS_DENIED` 映射 Access Token 问题。
- **错误码**：6 码闭集全识别，未知码回退 `ERR_EXECUTION`。

---

## 对话导出（JSONL）

⚙️ 配置面板 actions 区提供 `Export` 按钮（补漏性质的小功能）：点击把当前会话按行存为 JSONL（每行一条消息，含角色与正文），文件名 `tc-history-<时间戳>.jsonl`，方便留档与迁移；会话为空时点击仅提示、不生成文件。

