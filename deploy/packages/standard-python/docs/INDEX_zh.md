# standard-python 指令包索引（INDEX_zh.md）

> 本文件是 `standard-python/` 目录的**包清单**。具体每个包的安装步骤、指令表格与使用示例见各包目录内的 `README_zh.md`（中文）与 `README.md`（英文）。

## 一、本目录说明

- **定位**：Python 标准运行时指令包集合。每个包是可 `install` 即用的基础工具。
- **运行时**：标准运行时（Python），需在 A3+ Service 或 A9 全量运行时中安装使用。`web-utils` 为 Node 运行时（部署于腾讯云 CloudBase 云函数）。
- **依赖**：`tc-*` 基础工具除 `tc-table`（XLSX 可选 openpyxl）外均为零外部依赖、纯 stdlib；`image`（Pillow）、`skill-csv2json`（copilot bridge）、`ai-inference`（凭据注入，供应商/模型经配置注入、不硬编码）；地图与云服务类包（`bd-map`/`gd-map`/`tx-map`/`bd-cloud`/`aria2`/`vikunja`/`zhihu-cloud`）需要 `text_cli_modules/key/` 运行时模块与相应凭据；`web-utils` 依赖 `wx-server-sdk`。

## 二、包清单

| 包 ID | 版本 | 发行协议 | 形态 | 外部依赖 | 功能描述 |
| --- | --- | --- | --- | --- | --- |
| [`tc-math`](tc-math/) | 0.1.2 | MIT | tool | 无 | 路径管道用安全算术求值器。AST 校验，零依赖，仅用 math 标准库。 |
| [`tc-json`](tc-json/) | 0.1.2 | MIT | tool | 无 | 纯 stdlib JSON 结构原语：校验、美化、列出键、浅合并、点路径解析。零依赖。 |
| [`tc-diff`](tc-diff/) | 0.1.2 | MIT | tool | 无 | 路径管道用文本差异处理工具。行级统一差异、相似度比、补丁应用、词级差异。零外部依赖，纯 stdlib difflib。 |
| [`tc-datetime`](tc-datetime/) | 0.1.1 | MIT | tool | 无 | 路径管道用日期时间计算工具。now / offset / between / weekday / range / format。零外部依赖，纯 stdlib datetime。 |
| [`tc-sql`](tc-sql/) | 0.1.2 | MIT | tool | 无 | 统一 SQL 查询协议层。路由 + 鉴权 + 执行，任何数据拥有方通过声明加入。 |
| [`tc-table`](tc-table/) | 0.1.2 | MIT | tool | 无（XLSX 可选 openpyxl） | 路径管道用表格数据处理工具。读 CSV/TSV/XLSX → JSON 数组 → 筛选/排序/透视/合并 → 写回。 |
| [`tc-archive`](tc-archive/) | 0.1.2 | MIT | tool | 无 | 路径管道用压缩归档处理工具。创建、解压、列出归档文件 (zip/tar/tar.gz/tar.bz2/tar.xz)。零外部依赖，纯 stdlib zipfile + tarfile。路径白名单 + zip bomb 防御。 |
| [`tc-markdown`](tc-markdown/) | 0.1.2 | MIT | tool | 无 | 读取和解析 Markdown 文件：提取全文、标题结构、指定标题下的内容。路径受限访问保障安全。 |
| [`path-str`](path-str/) | 0.1.1 | MIT | tool | 无 | 路径管道组合用的字符串基础操作：模板替换、切分、合并。零依赖，仅标准库。 |
| [`weather`](weather/) | 0.1.1 | MIT | tool | 无 | 按城市与日期查询天气预报。Open-Meteo / wttr.in 双源免密降级，`lang` 控制输出语言（zh / en / ja）。 |
| [`image`](image/) | 0.1.2 | MIT | tool | Pillow | 图片信息读取、base64 编码、格式转换与缩放（基于 Pillow）。 |
| [`skill-csv2json`](skill-csv2json/) | 0.1.1 | MIT | tool | modules（handlers/skill_bridge） | 通过 ClawHub csv2json 技能将 CSV 文件转换为 JSON 数组。委托给 copilot Skill Bridge 通用适配器执行。 |
| [`ai-inference`](ai-inference/) | 0.1.2 | MIT | tool | 凭据（ai_api_key） | 文本推理与视觉分析，基于可配置的 AI 供应商。**仅分发机制**，不内置具体供应商 / 模型 / 端点——供应商名与模型均在 `config/model_aliases.json` 中配置、不硬编码，运行时经 `init_ai_handler()` / `set_model_registry()` 注入。 |
| [`aria2`](aria2/) | 0.1.1 | MIT | tool | requests + key 模块 | 通过 aria2 JSON-RPC API 管理下载任务。添加 HTTP/BT 下载、查询进度、控制任务。 |
| [`vikunja`](vikunja/) | 0.1.1 | MIT | tool | requests + key 模块 | 通过 Vikunja API 管理自托管任务。创建、更新、完成任务，组织到项目，使用标签，管理任务关系以供路径管道路由。 |
| [`bd-cloud`](bd-cloud/) | 0.1.1 | MIT | tool | requests + key 模块 | 百度云 API 封装：文字识别（OCR）、百科查询、AI 网络搜索、异步视频笔记。双凭据认证（bd-ocr + bd-qianfan）。 |
| [`bd-map`](bd-map/) | 0.1.1 | MIT | tool | key 模块 | 百度地图 HTTP API 封装：地理编码、IP 定位、路线规划（驾车/公交/步行/骑行）、坐标转换、静态图（标注/标签/折线叠加）。 |
| [`gd-map`](gd-map/) | 0.1.1 | MIT | tool | key 模块 | 高德地图 HTTP API 封装：地理编码、逆地理编码（含周边 POI）、静态图（标注/折线叠加）、多边形 POI 搜索。双凭据 + MD5 签名认证。 |
| [`tx-map`](tx-map/) | 0.1.1 | MIT | tool | key 模块 | 腾讯地图 HTTP API 封装：地理编码、逆地理编码、路线规划、静态图、IP 定位。双凭据认证 + 配额追踪。 |
| [`zhihu-cloud`](zhihu-cloud/) | 0.1.1 | MIT | tool | requests + key 模块 | 通过知乎开放平台 API 搜索知乎站内内容和全网索引。 |


## 三、版本与协议说明

- **版本号规则**：采用 Semver 版本子目录（`V0_1_1` / `V0_1_2`），包根下每个版本一个目录，最新版本目录即该包当前镜像。首发版本统一为 `0.1.1`，已有部分包迭代至 `0.1.2`。
- **MIT 协议**：本集合统一采用 MIT 许可证——可自由使用、修改、再分发，仅需保留版权与许可声明。
- **内容来源**：本目录各包为 `text-cli-package/releases/` 对应制品的干净副本（已剥离隐私数据），仅保留注释与文档，不含 `DESIGN.md` / `.dev` / 测试脚本。
