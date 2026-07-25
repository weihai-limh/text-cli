# 文档型（nocode）指令包开发指南

> 零代码。把领域经验写成 Markdown，变成可调用的 text-cli 指令。
> 制作方法见 [package-dev-guide_zh.md](package-dev-guide_zh.md)；schema 规范见 [package-publish-guide_zh.md](package-publish-guide_zh.md)。

> 💡 如果你的 Markdown 结构清晰，可以先用 `converter/readme_to_pkg.py` 生成起手骨架，再参考本指南补全。

---

## 0. 两种方式

| | 方式一：单文件 + 模板脚本 | 方式二：知识库 + 路径引擎 |
|---|---|---|
| 人的输入 | 一份 Markdown | knowledge/ 多文件 + index + path JSON |
| 匹配方式 | 关键词/字符串 | AI 语义推理 |
| 依赖 | 零（纯 Python 标准库） | `tc-markdown` + `ai_inference` |
| 适合场景 | 症状明确、关键词能覆盖 | 症状模糊、需要推理 |
| 入门 | 五分钟跑通 | 需要运行时支持 |

两种方式**递进**：方式一跑通后，同一份知识拆分就是方式二的 `knowledge/` 输入。

---

## 1. 方式一：单文件 + 模板脚本

### 1.1 Markdown 格式

```markdown
# 标题

## 指令定义
- 领域: <domain>
- 动作: <action>
- 触发词: <关键词,逗号分隔>
- 参数: <参数名,逗号分隔>

## 经验内容
### <分类A>
#### <子类A1>
- 原因/表现/症状: ...
- 急救/处理: ...
- 预防: ...

#### <子类A2>
...

### <分类B>
...
```

**示例**（盆栽急救手册）：

```markdown
# 盆栽常见问题急救手册

## 指令定义
- 领域: 家庭园艺
- 动作: 盆栽急救
- 触发词: 盆栽, 叶子黄, 烂根, 浇水, 绿萝, 多肉
- 参数: 植物名, 症状

## 经验内容
### 绿萝
#### 叶片发黄
- 原因：浇水过多或光照不足。
- 急救：立即停止浇水，移到散射光处，剪掉黄叶。
- 预防：春秋每周浇水1次，避免阳光直射。

#### 烂根
- 表现：根部变黑、变软，有异味。
- 急救：脱盆，剪去腐烂根系，换新土重栽。
- 预防：选用透气花盆，浇水见干见湿。
```

### 1.2 模板脚本

使用 `converter_template.py`（模板位置：`template/base_nocode/converter_template.py`）——一个可复用的骨架，将符合上述格式的 Markdown 转化为 text-cli 指令服务。已有填好的示例可直接体验：`template/base_nocode/zh/markdown_converter.py`（搭配 `盆栽急救手册.md`）。

**你需要改的部分（三处）**：

| 位置 | 改什么 |
|------|--------|
| `@register(...)` | domain、action、category、trust |
| `parse_experience_md()` 的解析正则 | 匹配你的 `###` / `####` 层级 |
| `handler()` 的检索逻辑 | 匹配你的参数结构 |

其余部分（文档解析、服务启动、返回格式）不需要改。

> 如果不想手改代码，可以让 AI 辅助——把 Markdown 文档和模板脚本一起交给 AI，描述你要的领域和参数，AI 帮你完成上述三处修改。

### 1.3 运行与验证

```bash
# 用骨架模板（需先修改三处）：
python template/base_nocode/converter_template.py 我的经验.md

# 或直接体验就绪示例：
cd template/base_nocode/zh
python markdown_converter.py 盆栽急救手册.md

# 验证
curl -X POST http://localhost:8000/text-cli/cli \
  -H "Content-Type: application/json" \
  -d '{"prompt": "AI:家庭园艺;盆栽急救,绿萝,叶片发黄"}'
```

---

## 2. 方式二：知识库 + 路径引擎

> 依赖 `tc-markdown` 和 `ai_inference` 需已安装。

### 2.1 文件结构

```
<package-id>/
├── schema.json              ← type: "nocode", runtime: "path"
├── path/
│   └── <name>.json          ← 路径定义（编排步骤）
├── knowledge/
│   ├── <问题A>.md           ← 经验文档
│   └── <问题B>.md
├── knowledge-index.md       ← 症状 → 文件名映射
└── README.md
```

### 2.2 schema.json

```json
{
  "id": "flower-care",
  "type": "nocode",
  "name": "Flower Care",
  "name_zh": "花卉养护",
  "runtime": "path",
  "version": "1.0.0",
  "category": "知识库",
  "locales": ["zh"],
  "trust": "community",
  "description": "Plant disease diagnosis using expert experience.",
  "description_zh": "基于专家经验的植物病害诊断。",
  "requires": {
    "tc_packages": ["tc-markdown", "ai_inference"]
  },
  "directives": [
    {
      "domain": "flower-care",
      "domain_zh": "花卉养护",
      "action": "diagnose",
      "action_zh": "��断",
      "usage": "flower-care;diagnose,<症状描述>",
      "usage_zh": "花卉养护;诊断,<症状描述>",
      "description": "Diagnose plant problems from symptom description.",
      "description_zh": "根据症状描述诊断植物问题。",
      "params": ["symptoms"],
      "params_desc": { "symptoms": "用自然语言描述症状" }
    }
  ]
}
```

### 2.3 knowledge-index.md

症状到文件名的映射表，AI 用它做语义匹配：

```markdown
根腐病.md ← 根变黑变软、有异味、茎基部腐烂
蚜虫.md   ← 嫩芽上有小虫子、叶子卷曲、有黏糊糊液体
黄叶病.md ← 新叶发黄但叶脉仍绿、老叶正常
NOMATCH   ← 以上都不像
```

格式：`<文件名.md> ← <症状关键词>`。末行 `NOMATCH` 是兜底。

### 2.4 knowledge/ 经验文档

```markdown
# 蚜虫

## 症状
- 嫩芽上聚着芝麻大小的虫子（绿/黑/黄）
- 被咬的嫩叶卷曲变形
- 叶面有黏糊糊的透明液体

## 处理方案
1. 数量少：棉签蘸酒精一个个擦掉
2. 数量多：洗衣粉水喷叶面（一小撮洗衣粉兑一升水，傍晚喷）
3. 隔天检查，如果还有活的重喷一次

## 预防
- 保持通风
- 控制氮肥用量
- 发现蚂蚁及时处理（蚂蚁会搬运蚜虫）
```

### 2.5 path/ 路径定义

四步流水线：索引 → AI 匹配 → 读取 → AI 诊断 → 兜底。

```json
{
  "steps": [
    {
      "id": "index",
      "instruction": "tc-markdown;read",
      "params": ["knowledge-index.md"]
    },
    {
      "id": "lookup",
      "instruction": "ai;infer",
      "params": [
        "根据索引匹配用户症状最像的病，输出一行纯JSON只含文件名。\n索引：\n{step.index.content}\n\n症状：{input.symptoms}\n\n输出示例：{\"file\":\"蚜虫.md\"} 不匹配：{\"file\":\"NOMATCH\"}"
      ]
    },
    {
      "id": "read",
      "instruction": "tc-markdown;read",
      "params": ["knowledge/{step.lookup.file}"]
    },
    {
      "id": "diagnose",
      "instruction": "ai;infer",
      "params": [
        "严格基于以下经验诊断，不编造。\n1.诊断 2.处理方案 3.预防建议\n\n经验：\n{step.read.content}\n\n症状：{input.symptoms}"
      ]
    },
    {
      "id": "fallback",
      "instruction": "ai;infer",
      "params": [
        "症状不在知识库范围内。基于通用知识给出建议。\n症状：{input.symptoms}"
      ],
      "if": "{step.lookup.file} == 'NOMATCH'"
    }
  ]
}
```

- `{input.symptoms}` — 用户输入
- `{step.index.content}` — 上一步 tc-markdown;read 的返回
- `{step.lookup.file}` — AI 返回 JSON 中的字段
- `"if"` — 条件执行：NOMATCH 时触发兜底

### 2.6 管道闭包原则

路径只做编排和插值。文件 IO、推理——全部通过指令完成：

| 不自己做的事 | 用什么指令 |
|-------------|-----------|
| 读文件 | `tc-markdown;read` |
| 语义匹配 | `ai;infer` |
| 诊断推理 | `ai;infer` |

### 2.7 安装与验证

```bash
curl -X POST http://localhost:28050/text-cli/cli \
  -H "Content-Type: application/json" \
  -d '{"prompt": "AI:text-cli;install,flower-care"}'

curl -X POST http://localhost:28050/text-cli/cli \
  -H "Content-Type: application/json" \
  -d '{"prompt": "AI:flower-care;diagnose,月季叶子卷曲有黏糊糊的液体"}'
```

---

## 3. 从方式一到方式二

**什么时候升级**：症状描述模糊、关键词匹配不准、知识条目增多后难以手工检索。

**升级步骤**：

1. **拆文档**：方式一 Markdown 中每个 `### 分类` → 一个 `knowledge/<分类>.md`
2. **写 index**：提取每篇的症状关键词 → `knowledge-index.md`
3. **写 schema**：`type: "nocode"`, `runtime: "path"`，声明 `tc-markdown` + `ai_inference` 依赖
4. **写 path**：索引 → 匹配 → 读取 → 诊断 → 兜底 的 JSON 步骤链
5. **安装**：`text-cli;install` 替代脚本启动
