# 零代码（nocode）开发指南

> 不用写代码。把你的经验写成 Markdown，变成人和 AI 都能调用的 text-cli 指令服务。

---

## 一、两种方式

你的 Markdown 经验文档可以通过两种方式变成指令服务：

| | 方式一：单文件 | 方式二：运行时 |
|---|---|---|
| 你要做的 | 写一份 Markdown（不改代码即可启动） | knowledge/ 多文件 + index + path JSON |
| 匹配方式 | 关键词字符串检索 | AI 语义推理 |
| 依赖 | 零（纯 Python 标准库） | `tc-markdown` + `ai-inference` |
| 启动 | `python converter_template.py <md文件>` | `text-cli;install` |
| 适合 | 症状明确、关键词能覆盖 | 症状模糊、需要推理 |

两种方式不是二选一——**方式一是零门槛起点，方式二是你拥有 text-cli 运行时之后，同一份知识可以嵌入的更完整的体系**。方式一的 Markdown 拆开就是方式二的 `knowledge/` 输入。

下文先带你体验方式一，再介绍方式二。

---

## 二、方式一：无运行时模式

> 零依赖。一份 Markdown + 一个模板脚本 = 一个 HTTP 指令服务。

### 2.1 现在就试试

盆栽急救是花店老板十年的经验笔记。你不需要懂代码——进去跑一下：

```bash
cd ../template/base_nocode/zh
python markdown_converter_zh.py 盆栽急救手册_zh.md
```

启动后：

```bash
curl -X POST http://localhost:8000/text-cli/cli \
  -H "Content-Type: application/json" \
  -d '{"prompt": "AI:家庭园艺;盆栽急救,绿萝,叶片发黄"}'
```

响应：

```json
{
  "rst_types": "text",
  "rst_data": {
    "status": "ok",
    "category": "绿萝",
    "sub": "叶片发黄",
    "content": "- 原因: 浇水过多或光照不足...\n- 处理: ...\n- 鉴别: ...\n- 教训: ..."
  },
  "rst_err": ""
}
```

返回绿萝叶片发黄的原因、处理方案、鉴别诊断和预防建议。一份 Markdown，一个能用的服务。人和 AI 通过同一个端点消费。


### 2.2 把你的经验变成服务

写一份 Markdown（参考 `../template/base_nocode/template.md` 或 `../template/base_nocode/template_zh.md`）：

```markdown
## 指令定义
- 领域: 汽车维修
- 动作: 诊断
- 触发词: 发动机, 刹车, 异响
- 参数: 部位, 症状
- 来源: 王师傅口述,二十年汽修经验     # 可选 — 知识出处
- 核实: 李工,2025-08-01                 # 可选 — 核实人与日期
- 过期: 2026-12-31                       # 可选 — 过期日期
- 状态: stable                           # 可选 — draft | stable | deprecated

## 经验内容
### 发动机
#### 无法启动
- 原因: 电瓶亏电或起动机故障。
- 处理: 搭电或更换电瓶。检查起动机继电器。
- 预防: 每 3-5 年更换电瓶。
- 鉴别: ...                              # 可选 — 如何与相似问题区分
- 教训: ...                              # 可选 — 血泪教训
```

> `来源`/`核实`/`过期`/`状态` 为可选字段——这些信息属于知识生产工作流，可能在数据传递中被清洗。代码有则透传（出现在 schema 中），无则不影响服务运行。`鉴别`/`教训` 为内容约定字段，写在条目中即可，解析器不做特殊处理。

不改代码，直接启动：

```bash
python ../template/base_nocode/converter_template.py 汽车维修手册.md
```

脚本自动从 Markdown 的 `## 指令定义` 中提取领域和动作。如果需要覆盖 Markdown 中的值，改顶部变量：

```python
Domain = "汽车维修"       # 显式设置则覆盖 Markdown 中的值
Action = "诊断"
Host = "0.0.0.0"          # 绑定地址
Port = 8000               # 监听端口
```

`Host` 和 `Port` 也可通过命令行参数覆盖：

```bash
python ../template/base_nocode/converter_template.py 汽车维修手册.md --port 9000
```

服务启动。`AI:汽车维修;诊断,发动机,无法启动` → 返回你的经验。

### 2.3 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/text-cli/cli` | POST | 执行指令（`AI:域;动作,参数`） |
| `/text-cli/cli` | POST | 指令发现（`AI:text-cli;query,json`） |
| `/text-cli/schema` | GET | 指令 schema（含可信度信息） |
| `/text-cli/health` | GET | 健康检查 |

查询示例：

```bash
# 精确匹配
curl -X POST http://localhost:8000/text-cli/cli \
  -H "Content-Type: application/json" \
  -d '{"prompt": "AI:汽车维修;诊断,发动机,无法启动"}'

# 列出该分类下所有子类
curl -X POST http://localhost:8000/text-cli/cli \
  -H "Content-Type: application/json" \
  -d '{"prompt": "AI:汽车维修;诊断,发动机"}'

# 列出所有分类
curl -X POST http://localhost:8000/text-cli/cli \
  -H "Content-Type: application/json" \
  -d '{"prompt": "AI:汽车维修;诊断"}'

# 查看 schema（含来源/核实/过期/状态等可信度信息）
curl http://localhost:8000/text-cli/schema

# 指令发现（与 schema 端点返回相同内容）
curl -X POST http://localhost:8000/text-cli/cli \
  -H "Content-Type: application/json" \
  -d '{"prompt": "AI:text-cli;query,json"}'
```

精确匹配响应：

```json
{
  "rst_data": {
    "status": "ok",
    "category": "发动机",
    "sub": "无法启动",
    "content": "- 原因: ...\n- 处理: ...\n- 鉴别: ...\n- 教训: ..."
  }
}
```

降级匹配（症状未精确命中）：

```json
{
  "rst_data": {
    "status": "ok",
    "category": "发动机",
    "sub": null,
    "items": [
      {"sub": "无法启动", "content": "..."},
      {"sub": "异响", "content": "..."}
    ]
  }
}
```

### 2.4 自定义检索逻辑

默认的 `分类 → 子分类` 两级检索匹配大部分场景。如果需要不同的参数结构，改 `[Custom 3/3]` 区的 `handler()` 函数。handler 返回 dict（直接作为 `rst_data`）：

```
无参数    → {"status": "ok", "entry_count": N, "categories": [...]}
一个参数  → {"status": "ok", "category": "...", "subs": [...]}
两个参数  → {"status": "ok", "category": "...", "sub": "...", "content": "..."}
          找不到则降级 → {"status": "ok", "category": "...", "sub": null, "items": [...]}
```

改完重启生效。参考 `zh/markdown_converter_zh.py` 看一个自包含的完整实例。

### 2.5 多语言支持

模板脚本语言无关——字段名通过 `FIELD_LABELS` 配置驱动。默认支持中文和英文。需要其他语言时，在 `FIELD_LABELS` 中添加一个语言子树即可：

```python
FIELD_LABELS = {
    "en": { "domain": "Domain", "action": "Action", ... },
    "zh": { "domain": "领域", "action": "动作", ... },
    # "ja": { "domain": "領域", "action": "動作", ... },  ← 取消注释并填入
}
```

完整语言参考库见 `../template/base_nocode/field_labels.json`（含中/英/法/阿/西/俄/日/韩/繁中）。加语言 = 加一行配置，解析逻辑零改动。

### 2.6 加 token 鉴权

如果需要限制谁能访问，改顶部两个变量：

```python
AuthEnabled = True
ServiceToken = "my-secret"
```

调用方须在请求头带 `Service-token: my-secret`。token 不匹配返回 `ACCESS_DENIED`。

---

## 三、方式二：运行时模式

> 前提：你已部署 text-cli 运行时，且 `tc-markdown` 和 `ai-inference` 两个指令包已安装。

方式二不是多写代码——你的 Markdown 经验知识不变。它多出的是运行时赋予的能力：AI 语义推理、指令发现、路径编排、聚合降级。方式一的同一份知识拆成多文件，加一份路径定义和包声明，就变成了运行时可感知的指令包。

### 3.1 核心区别

方式一是一个独立的 HTTP 服务。方式二是运行时可调度的一级能力——可被 `text-cli;query` 发现、可参与路径编排、可被聚合降级。

同一份知识，不同的部署形态：

```
方式一                          方式二
盆栽急救手册_zh.md  ──拆开──→  knowledge/
  （一份大文档）                   ├── 绿萝-叶片发黄.md
                                  ├── 绿萝-烂根.md
                                  ├── 蚜虫.md
                                  └── ...
                              + knowledge-index.md  ← AI 用这个匹配
                              + path/diagnose.json   ← 编排步骤
                              + schema.json          ← 包声明
```

### 3.2 从方式一升级

已有方式一的 Markdown？五步升级：

1. **拆文档**：每个 `### 分类` → `knowledge/<分类>.md`
2. **写 index**：提取每篇的症状关键词 → `knowledge-index.md`
3. **写 schema**：`type: "nocode"`, `runtime: "path"`
4. **写 path**：四步流水线 JSON（见 3.4）
5. **安装**：
```
AI:text-cli;install,tc-markdown
AI:text-cli;install,ai-inference
AI:text-cli;install,<package-id>
```


> 模板和完整示例：`../template/runtime_nocode/nocode-template/` + `../template/runtime_nocode/nocode-example-zh/`

### 3.3 文件结构

```
<package-id>/
├── schema.json
├── path/diagnose.json
├── knowledge/              ← 从方式一拆出来的经验文档
│   ├── 蚜虫.md
│   └── 根腐.md
├── knowledge-index.md      ← 症状 → 文件名
└── README.md
```

### 3.4 路径定义

路径引擎用 `tc-markdown;read` 读文件、`ai;infer` 做推理——路径本身只做编排和插值：

```json
{
  "type": "pipeline",
  "default_source": "http://localhost:28050/text-cli/cli",
  "requires": ["tc-markdown;read", "ai;infer"],
  "steps": [
    {"id": "index",    "instruction": "tc-markdown;read,knowledge-index.md"},
    {"id": "lookup",   "instruction": "ai;infer,根据索引匹配症状...", "output_as": "lookup"},
    {"id": "read",     "instruction": "tc-markdown;read,knowledge/{lookup.file}"},
    {"id": "diagnose", "instruction": "ai;infer,基于经验诊断...",   "output_as": "diagnose"},
    {"id": "fallback", "instruction": "ai;infer,通用建议...", "if": "{lookup.file} == 'NOMATCH'"}
  ]
}
```

完整定义见 `../template/runtime_nocode/nocode-example-zh/path/diagnose.json`。

### 3.5 安装与验证

```bash
curl -X POST http://localhost:28050/text-cli/cli \
  -H "Content-Type: application/json" \
  -d '{"prompt": "AI:text-cli;install,flower-care"}'

curl -X POST http://localhost:28050/text-cli/cli \
  -H "Content-Type: application/json" \
  -d '{"prompt": "AI:flower-care;diagnose,叶子卷曲有黏糊糊的液体"}'
```

---

> 更多细节：`../template/base_nocode/docs/README_zh.md`（方式一模板说明书）。
