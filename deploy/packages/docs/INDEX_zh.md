# open_text_cli 指令包索引（INDEX_zh.md）

> 本文件是 `open_text_cli/` 集合的**登记册 + 示例导航**。具体每个包的安装步骤、指令表格与使用示例见各包目录内的 `README_zh.md`（中文）与 `README.md`（英文）。

## 一、本目录说明

- **定位**：随 text-cli 运行时分发的 **MIT 起步包示例集**（非模板库）。每个标准运行时的包是可 `install` 即用的基础工具。
- **分发**：具体分发由 `scripts/build-all.py` 从本目录全量复制到 `deploy/packages/` 完成。


## 二、包清单（总表）

> 借助「运行时 / 外部依赖」列即可分区检索示例：标准运行时 / 旁路运行时、零依赖 / Pillow / modules（copilot 桥接）/ 凭据 + 运行时模块。
> 每个包目录内均含 `README_zh.md` 与 `README.md` 双语文档。

| 包 ID | 版本 | 发行协议 | 形态 | 运行时 | 外部依赖 | 功能描述 |
| --- | --- | --- | --- | --- | --- | --- |
| [`tc-math`](tc-math/) | 0.1.1 | MIT | tool | 标准运行时 | 无 | 路径管道用安全算术求值器。AST 校验，零依赖，仅用 math 标准库。 |
| [`tc-json`](tc-json/) | 0.1.1 | MIT | tool | 标准运行时 | 无 | 纯 stdlib JSON 结构原语：校验、美化、列出键、浅合并、点路径解析。零依赖。 |
| [`tc-diff`](tc-diff/) | 0.1.1 | MIT | tool | 标准运行时 | 无 | 路径管道用文本差异处理工具。行级统一差异、相似度比、补丁应用、词级差异。零外部依赖，纯 stdlib difflib。 |
| [`tc-sql`](tc-sql/) | 0.1.1 | MIT | tool | 标准运行时 | 无 | 统一 SQL 查询协议层。路由 + 鉴权 + 执行，任何数据拥有方通过声明加入。 |
| [`tc-table`](tc-table/) | 0.1.1 | MIT | tool | 标准运行时 | 无（XLSX 可选 openpyxl） | 路径管道用表格数据处理工具。读 CSV/TSV/XLSX → JSON 数组 → 筛选/排序/透视/合并 → 写回。 |
| [`tc-archive`](tc-archive/) | 0.1.1 | MIT | tool | 标准运行时 | 无 | 路径管道用压缩归档处理工具。创建、解压、列出归档文件 (zip/tar/tar.gz/tar.bz2/tar.xz)。零外部依赖，纯 stdlib zipfile + tarfile。路径白名单 + zip bomb 防御。 |
| [`tc-markdown`](tc-markdown/) | 0.1.1 | MIT | tool | 标准运行时 | 无 | 读取和解析 Markdown 文件：提取全文、标题结构、指定标题下的内容。路径受限访问保障安全。 |
| [`image`](image/) | 0.1.1 | MIT | tool | 标准运行时 | Pillow | 图片信息读取、base64 编码、格式转换与缩放（基于 Pillow）。 |
| [`skill-csv2json`](skill-csv2json/) | 0.1.1 | MIT | tool | 标准运行时(copilot) | modules（handlers/skill_bridge） | 通过 ClawHub csv2json 技能将 CSV 文件转换为 JSON 数组。委托给 copilot Skill Bridge 通用适配器执行。 |
| [`web-utils`](web-utils/) | 0.1.1 | MIT | tool | 旁路运行时 | CloudBase | Web 工具（IP 查询、XOR 加密），以 CloudBase SCF 旁路运行时提供。 |
| [`ai-inference`](ai-inference/) | 0.1.1 | MIT | tool | 标准运行时 | 凭据 + 运行时模块 | 文本推理与视觉分析，基于可配置的 AI 供应商。**仅分发机制**，不内置具体供应商 / 模型 / 端点——供应商名与模型均在 `config/model_aliases.json` 中配置、不硬编码，运行时经 `init_ai_handler()` / `set_model_registry()` 注入。 |

## 三、版本与协议说明

- **版本号规则**：首发版本统一为 `0.1.1`（Semver）。本目录不含版本子目录，包根即最新镜像。
- **MIT 协议**：本集合统一采用 MIT 许可证——可自由使用、修改、再分发，仅需保留版权与许可声明。与 text-cli 引擎许可证一致，可随运行时公开分发。
- **内容来源**：本目录各包为 `text-cli-package/releases/` 对应制品的干净副本（已剥离隐私数据），仅保留注释与文档，不含 `DESIGN.md` / `.dev` / 测试脚本。
