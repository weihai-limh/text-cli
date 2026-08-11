# 无代码路径模板

复制此模板，替换占位符，添加你的知识——不需要写一行代码，你就有了一个可调用的 AI 诊断指令包。

> 完整示例见 `../nocode-example-zh/`（盆栽急救诊断）。

## 快速开始

1. `cp -r nocode-template my-package`
2. 替换 `schema.json` 和 `path/diagnose.json` 中所有 `{PLACEHOLDER}`
3. 在 `knowledge/` 中写入你的知识文档，删除 `example.md`
4. 填写 `knowledge-index.md`
5. `AI:text-cli;install,{PACKAGE_ID}`

## 依赖

- text-cli 包：`tc-markdown`、`ai-inference`
- 运行时：A4+（路径引擎）

## 原理

```
用户: {DOMAIN};{ACTION},{症状描述}

路径引擎:
  1. tc-markdown;读取 → knowledge-index.md  （症状→文档映射）
  2. ai;推理 → 语义匹配 → 最佳文档
  3. tc-markdown;读取 → knowledge/{文档}（专家经验）
  4. ai;推理 → 诊断 + 处理方案 + 预防建议
  5. NOMATCH → 兜底通用建议
```

## 架构

```
nocode-template/
├── schema.json                ← 指令声明（{占位符}）
├── path/
│   └── diagnose.json          ← 5 步流水线（{占位符}）
├── knowledge/
│   └── example.md             ← 格式参考（完成后删除）
├── knowledge-index.md         ← 症状 → 文件映射
├── TEMPLATE_INSTRUCTIONS.md   ← 详细替换清单
└── README*.md
```
