# text-cli 指令包开发导航

`src/text_cli/` 是指令包生态的开发入口——包含开发文档、起手模板、以及开源包源码。

---

## 目录总览

```
src/text_cli/
├── base_text-cli/        ← 指令包开发框架（文档 + 模板）
└── open_text_cli/        ← 开源指令包源码（MIT 协议，随运行时分发）
```

---

## 文档

| 文档 | 面向 | 说明 |
|------|------|------|
| [package-dev-guide_zh.md](base_text-cli/docs/package-dev-guide_zh.md) | 包开发者 | 标准指令包开发全流程——工具函数、在线 API、容器 API、copilot 四种形态 |
| [package-nocode-guide_zh.md](base_text-cli/docs/package-nocode-guide_zh.md) | 经验持有者（非开发者） | 零代码指令包——Markdown 即指令，两种递进方式 |
| [package-publish-guide_zh.md](base_text-cli/docs/package-publish-guide_zh.md) | 包作者 | Schema 规范 Checklist + 反例 + 返回信封约定 |
| [package-dev-other-guide_zh.md](base_text-cli/docs/package-dev-other-guide_zh.md) | 旁路运行时开发者 | CloudBase SCF 等云函数平台的指令包开发 |

---

## 模板

指令包起手骨架，按运行时分类：

| 模板目录 | 目标运行时 | 语言 | 说明 |
|------|------|------|------|
| [template/runtime_standard/](base_text-cli/template/runtime_standard/) | service / copilot | Python | 标准运行时起手——schema.json + handler.py 骨架（待填充） |
| [template/runtime_bypass/](base_text-cli/template/runtime_bypass/) | CloudBase SCF | Node.js | 旁路运行时起手——index.js + instructions/ + package.json（待填充） |
| [template/runtime_nocode/zh/](base_text-cli/template/runtime_nocode/zh/) | service | 中文 Markdown | nocode 运行时起手——中文文档型包模板（待填充） |
| [template/base_nocode/zh/](base_text-cli/template/base_nocode/zh/) | — | Python + Markdown | nocode 基础模板——转换器脚本 + 示例手册 |

### 当前可用模板

| 模板 | 说明 |
|------|------|
| [base_nocode/converter_template.py](base_text-cli/template/base_nocode/converter_template.py) | 通用 Markdown→指令 转换器骨架（英文） |
| [base_nocode/zh/markdown_converter.py](base_text-cli/template/base_nocode/zh/markdown_converter.py) | 中文 Markdown 转换器 |
| [base_nocode/zh/盆栽急救手册.md](base_text-cli/template/base_nocode/zh/盆栽急救手册.md) | nocode 包示例——领域经验写成 Markdown |

---

## 开源指令包

`open_text_cli/` —— MIT 协议开源包源码，经 `scripts/build-all.py` 分发到 `deploy/packages/`，随标准运行时分发。

```
src/text_cli/open_text_cli/
├── docs/        ← 开源指令包目录
└── <指令包>/        ← 开源指令包源码（MIT 协议）
```
---

## 快速开始

按你的角色选择入口：

- **我要写一个新指令包** → [package-dev-guide_zh.md](base_text-cli/docs/package-dev-guide_zh.md) §二，"工具函数包：从零到一"
- **我只有经验、不会写代码** → [package-nocode-guide_zh.md](base_text-cli/docs/package-nocode-guide_zh.md) §1，"单文件 + 模板脚本"
- **我要把包发布到 CloudBase** → [package-dev-other-guide_zh.md](base_text-cli/docs/package-dev-other-guide_zh.md) §1
- **我的包写好了，要检查是否符合规范** → [package-publish-guide_zh.md](base_text-cli/docs/package-publish-guide_zh.md) §2，"schema.json 规范"
