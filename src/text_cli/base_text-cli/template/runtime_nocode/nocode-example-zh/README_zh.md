# 盆栽急救诊断

**无代码指令包示例**——一个花店老板的经验变成了可调用的 AI 诊断服务。

> 想创建你自己的无代码指令包？看 `../nocode-template/` 模板。

## 安装

```
AI:text-cli;install,nocode-zh
```

## 依赖

- text-cli 包：`tc-markdown`、`ai-inference`
- 运行时：path engine（A4+）
- 无 pip 依赖，无需凭据

## 指令

| 指令 | 说明 |
|------|------|
| `家庭园艺;诊断,<症状描述>` | 根据症状描述诊断盆栽问题，给出处理方案和预防建议 |

## 原理

```
用户: 家庭园艺;诊断,月季叶子从下往上黄，一碰就掉

路径引擎:
  1. tc-markdown;读取 → knowledge-index.md（症状→病名映射）
  2. ai;推理 → 语义匹配 → "根腐病.md"
  3. tc-markdown;读取 → knowledge/根腐病.md（专家经验）
  4. ai;推理 → 诊断 + 处理方案 + 预防建议
  5. NOMATCH → 兜底通用植物建议
```

## 架构

```
nocode-example-zh/
├── schema.json           ← 指令声明 (type: nocode, runtime: path)
├── knowledge/            ← 嵌入式经验文档（6 种盆栽常见问题）
│   ├── 蚜虫.md
│   ├── 根腐病.md
│   ├── 黄叶病.md
│   ├── 白粉病.md
│   ├── 浇水烂根.md
│   └── 光照不足.md
├── knowledge-index.md    ← 症状 → 文档映射（AI 用此做语义匹配）
└── path/
    └── diagnose.json     ← 路径定义（5 步流水线：索引→匹配→读取→诊断→兜底）
```

## 创建你自己的

使用 `../nocode-template/` 模板——占位符已标好，拷走替换即可。
