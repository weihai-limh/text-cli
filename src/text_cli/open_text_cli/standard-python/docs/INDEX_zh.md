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

## 四、指令示例

安装任一包后，向运行时发送带 `AI:` 前缀的文本指令即可调用。指令格式 `AI:domain;action,<参数...>`，`domain`/`action` 可使用各包 `schema.json` 中声明的 `_zh` 中文别名（如 `AI:计算;求值,2+3*4`）。handler 返回的 dict 直接作为响应信封的 `rst_data`。以下按包清单次序给出各包的代表指令与响应，每条英文指令下方附中文别名等价写法：

```
# tc-math — 安全算术求值
AI:tc-math;eval,2+3*4 → {"rst_types":"text","rst_data":{"status":"ok","result":14},"rst_err":""}
AI:计算;求值,2+3*4 → {"rst_types":"text","rst_data":{"status":"ok","result":14},"rst_err":""}
AI:tc-math;eval,sqrt(3**2+4**2) → {"rst_types":"text","rst_data":{"status":"ok","result":5.0},"rst_err":""}
AI:计算;求值,sqrt(3**2+4**2) → {"rst_types":"text","rst_data":{"status":"ok","result":5.0},"rst_err":""}

# tc-json — 结构原语
AI:tc-json;parse,{"name":"text-cli"} → {"rst_types":"text","rst_data":{"status":"ok","result":{"name":"text-cli"}},"rst_err":""}
AI:tc-json;解析,{"name":"text-cli"} → {"rst_types":"text","rst_data":{"status":"ok","result":{"name":"text-cli"}},"rst_err":""}
AI:tc-json;validate,'{"a":1}' → {"rst_types":"text","rst_data":{"status":"ok","valid":true},"rst_err":""}
AI:tc-json;校验,'{"a":1}' → {"rst_types":"text","rst_data":{"status":"ok","valid":true},"rst_err":""}

# tc-diff — 文本差异
AI:tc-diff;similarity,hello world,hello there → {"rst_types":"text","rst_data":{"status":"ok","similarity":0.53},"rst_err":""}
AI:文本差异;相似度,hello world,hello there → {"rst_types":"text","rst_data":{"status":"ok","similarity":0.53},"rst_err":""}
AI:tc-diff;unified,line a,line b → {"rst_types":"text","rst_data":{"status":"ok","has_diff":true,"similarity":0.0},"rst_err":""}
AI:文本差异;统一差异,line a,line b → {"rst_types":"text","rst_data":{"status":"ok","has_diff":true,"similarity":0.0},"rst_err":""}

# tc-datetime — 日期时间
AI:tc-datetime;now → {"rst_types":"text","rst_data":{"status":"ok","date":"2026-08-12T09:30:00","timezone":"UTC"},"rst_err":""}
AI:日期时间;现在 → {"rst_types":"text","rst_data":{"status":"ok","date":"2026-08-12T09:30:00","timezone":"UTC"},"rst_err":""}
AI:tc-datetime;between,2026-01-01,2026-01-31,days → {"rst_types":"text","rst_data":{"status":"ok","result":30},"rst_err":""}
AI:日期时间;间距,2026-01-01,2026-01-31,days → {"rst_types":"text","rst_data":{"status":"ok","result":30},"rst_err":""}

# tc-sql — 统一 SQL 协议层
AI:tc-sql;tables,main → {"rst_types":"text","rst_data":{"status":"ok","reason":["users","orders"]},"rst_err":""}
AI:SQL查询;表列表,main → {"rst_types":"text","rst_data":{"status":"ok","reason":["users","orders"]},"rst_err":""}
AI:tc-sql;query,main,{"table":"users","columns":["id","name"],"limit":10} → {"rst_types":"text","rst_data":{"status":"ok","reason":[{"id":1,"name":"text-cli"}]},"rst_err":""}
AI:SQL查询;查询,main,{"table":"users","columns":["id","name"],"limit":10} → {"rst_types":"text","rst_data":{"status":"ok","reason":[{"id":1,"name":"text-cli"}]},"rst_err":""}

# tc-table — 表格处理
AI:tc-table;read,data.csv → {"rst_types":"text","rst_data":{"status":"ok","columns":["name","age"],"row_count":2,"rows":[{"name":"a","age":1},{"name":"b","age":2}]},"rst_err":""}
AI:表格;读取,data.csv → {"rst_types":"text","rst_data":{"status":"ok","columns":["name","age"],"row_count":2,"rows":[{"name":"a","age":1},{"name":"b","age":2}]},"rst_err":""}
AI:tc-table;filter,[{"name":"a","age":1},{"name":"b","age":2}],{"where":["age",">",1]} → {"rst_types":"text","rst_data":{"status":"ok","rows":[{"name":"b","age":2}],"count":1,"filtered_count":1},"rst_err":""}
AI:表格;筛选,[{"name":"a","age":1},{"name":"b","age":2}],{"where":["age",">",1]} → {"rst_types":"text","rst_data":{"status":"ok","rows":[{"name":"b","age":2}],"count":1,"filtered_count":1},"rst_err":""}

# tc-archive — 压缩归档
AI:tc-archive;create,out.zip,data → {"rst_types":"text","rst_data":{"status":"ok","path":"out.zip","entries":["data/a.txt"],"count":1},"rst_err":""}
AI:压缩归档;创建归档,out.zip,data → {"rst_types":"text","rst_data":{"status":"ok","path":"out.zip","entries":["data/a.txt"],"count":1},"rst_err":""}
AI:tc-archive;extract,out.zip,dist → {"rst_types":"text","rst_data":{"status":"ok","path":"dist","entries":["data/a.txt"],"count":1},"rst_err":""}
AI:压缩归档;解压归档,out.zip,dist → {"rst_types":"text","rst_data":{"status":"ok","path":"dist","entries":["data/a.txt"],"count":1},"rst_err":""}
AI:tc-archive;list,out.zip → {"rst_types":"text","rst_data":{"status":"ok","entries":["data/a.txt"],"count":1},"rst_err":""}
AI:压缩归档;列出内容,out.zip → {"rst_types":"text","rst_data":{"status":"ok","entries":["data/a.txt"],"count":1},"rst_err":""}

# tc-markdown — Markdown 读取
AI:tc-markdown;read,doc.md → {"rst_types":"text","rst_data":{"status":"ok","reason":"# Title\ncontent"},"rst_err":""}
AI:tc-markdown;读取,doc.md → {"rst_types":"text","rst_data":{"status":"ok","reason":"# Title\ncontent"},"rst_err":""}
AI:tc-markdown;headings,doc.md → {"rst_types":"text","rst_data":{"status":"ok","reason":[{"level":1,"text":"Title","line":1}]},"rst_err":""}
AI:tc-markdown;标题,doc.md → {"rst_types":"text","rst_data":{"status":"ok","reason":[{"level":1,"text":"Title","line":1}]},"rst_err":""}
AI:tc-markdown;section,doc.md,Intro → {"rst_types":"text","rst_data":{"status":"ok","reason":"intro body"},"rst_err":""}
AI:tc-markdown;章节,doc.md,Intro → {"rst_types":"text","rst_data":{"status":"ok","reason":"intro body"},"rst_err":""}

# path-str — 路径字符串
AI:path-str;template,{base}/out/{0},base=/tmp,0=file → {"rst_types":"text","rst_data":{"status":"ok","result":"/tmp/out/file"},"rst_err":""}
AI:路径字符串;模板,{base}/out/{0},base=/tmp,0=file → {"rst_types":"text","rst_data":{"status":"ok","result":"/tmp/out/file"},"rst_err":""}
AI:path-str;split,'a/b/c','/' → {"rst_types":"text","rst_data":{"status":"ok","parts":["a","b","c"],"count":3},"rst_err":""}
AI:路径字符串;切分,'a/b/c','/' → {"rst_types":"text","rst_data":{"status":"ok","parts":["a","b","c"],"count":3},"rst_err":""}
AI:path-str;join,'["a","b","c"]','/' → {"rst_types":"text","rst_data":{"status":"ok","result":"a/b/c"},"rst_err":""}
AI:路径字符串;合并,'["a","b","c"]','/' → {"rst_types":"text","rst_data":{"status":"ok","result":"a/b/c"},"rst_err":""}

# weather — 天气查询（免密双源降级）
AI:weather;query,威海 → {"rst_types":"text","rst_data":{"status":"ok","source":"open-meteo","city":"威海","date":"2026-08-12","temp_min":24,"temp_max":30,"weather_desc":"晴","lang":"zh"},"rst_err":""}
AI:天气;查询,威海 → {"rst_types":"text","rst_data":{"status":"ok","source":"open-meteo","city":"威海","date":"2026-08-12","temp_min":24,"temp_max":30,"weather_desc":"晴","lang":"zh"},"rst_err":""}

# image — 图片处理（需 Pillow）
AI:image;info,photo.png,json → {"rst_types":"text","rst_data":{"status":"ok","width":1920,"height":1080,"format":"PNG","size_bytes":123456,"mode":"RGB","frames":1,"result":"photo.png"},"rst_err":""}
AI:图片;信息,photo.png,json → {"rst_types":"text","rst_data":{"status":"ok","width":1920,"height":1080,"format":"PNG","size_bytes":123456,"mode":"RGB","frames":1,"result":"photo.png"},"rst_err":""}
AI:image;encode,photo.png → {"rst_types":"text","rst_data":{"status":"ok","cache_key":"cache://img/abc","original":"photo.png","encoded":"base64...","expires_seconds":3600,"result":"cache://img/abc"},"rst_err":""}
AI:图片;编码,photo.png → {"rst_types":"text","rst_data":{"status":"ok","cache_key":"cache://img/abc","original":"photo.png","encoded":"base64...","expires_seconds":3600,"result":"cache://img/abc"},"rst_err":""}
AI:image;convert,in.png,jpg → {"rst_types":"text","rst_data":{"status":"ok","path":"out.jpg","width":1920,"height":1080,"format":"JPEG","result":"out.jpg"},"rst_err":""}
AI:图片;转换,in.png,jpg → {"rst_types":"text","rst_data":{"status":"ok","path":"out.jpg","width":1920,"height":1080,"format":"JPEG","result":"out.jpg"},"rst_err":""}
AI:image;resize,in.png,800,600 → {"rst_types":"text","rst_data":{"status":"ok","path":"out.png","width":800,"height":600,"original_width":1920,"original_height":1080,"result":"out.png"},"rst_err":""}
AI:图片;缩放,in.png,800,600 → {"rst_types":"text","rst_data":{"status":"ok","path":"out.png","width":800,"height":600,"original_width":1920,"original_height":1080,"result":"out.png"},"rst_err":""}

# ai-inference — AI 推理（仅机制，供应商经配置注入）
AI:ai-inference;infer,法国的首都是哪里?,auto → {"rst_types":"text","rst_data":{"status":"ok","result":"法国的首都是巴黎。"},"rst_err":""}
AI:AI推理;推理,法国的首都是哪里?,auto → {"rst_types":"text","rst_data":{"status":"ok","result":"法国的首都是巴黎。"},"rst_err":""}
AI:ai-inference;vision,描述这张图片,https://example.com/photo.jpg,quality → {"rst_types":"text","rst_data":{"status":"ok","result":"图片显示山脉上方的日落..."},"rst_err":""}
AI:AI推理;视觉,描述这张图片,https://example.com/photo.jpg,quality → {"rst_types":"text","rst_data":{"status":"ok","result":"图片显示山脉上方的日落..."},"rst_err":""}
AI:ai-inference;infer,总结要点,cache:abc123 → {"rst_types":"text","rst_data":{"status":"ok","result":"...","cache_key":"def456"},"rst_err":""}

# skill-csv2json — CSV 转 JSON（copilot bridge）
AI:skill-csv2json;convert,data.csv → {"rst_types":"text","rst_data":{"status":"ok","data":[{"name":"a","age":1},{"name":"b","age":2}],"count":2},"rst_err":""}
AI:skill-csv2json;转换,data.csv → {"rst_types":"text","rst_data":{"status":"ok","data":[{"name":"a","age":1},{"name":"b","age":2}],"count":2},"rst_err":""}

# aria2 — 下载管理（需 requests + aria2 凭据）
AI:aria2;add-uri,{"uris":["https://example.com/a.zip"],"options":{"out":"a.zip"}} → {"rst_types":"text","rst_data":{"status":"ok","gid":"d7c...","reason":"added"},"rst_err":""}
AI:aria2;添加下载,{"uris":["https://example.com/a.zip"],"options":{"out":"a.zip"}} → {"rst_types":"text","rst_data":{"status":"ok","gid":"d7c...","reason":"added"},"rst_err":""}
AI:aria2;status,d7c1e2f3 → {"rst_types":"text","rst_data":{"status":"ok","gid":"d7c1e2f3","reason":{"state":"active","progress":0.42,"speed":102400}},"rst_err":""}
AI:aria2;下载状态,d7c1e2f3 → {"rst_types":"text","rst_data":{"status":"ok","gid":"d7c1e2f3","reason":{"state":"active","progress":0.42,"speed":102400}},"rst_err":""}
AI:aria2;active → {"rst_types":"text","rst_data":{"status":"ok","count":2,"downloads":[{"gid":"d7c...","progress":0.42},{"gid":"a1b...","progress":0.10}],"reason":""},"rst_err":""}
AI:aria2;global-stat → {"rst_types":"text","rst_data":{"status":"ok","download_speed":102400,"upload_speed":0,"num_active":2,"num_waiting":0,"num_stopped":5,"reason":""},"rst_err":""}

# vikunja — 任务管理（需 requests + vikunja 凭据）
AI:vikunja;create-task,{"title":"写周报","priority":3,"due_date":"2026-08-15"} → {"rst_types":"text","rst_data":{"status":"ok","id":42,"title":"写周报","priority":3,"done":false,"due_date":"2026-08-15","reason":""},"rst_err":""}
AI:vikunja;创建任务,{"title":"写周报","priority":3,"due_date":"2026-08-15"} → {"rst_types":"text","rst_data":{"status":"ok","id":42,"title":"写周报","priority":3,"done":false,"due_date":"2026-08-15","reason":""},"rst_err":""}
AI:vikunja;list-tasks → {"rst_types":"text","rst_data":{"status":"ok","count":2,"total":2,"tasks":[{"id":42,"title":"写周报","done":false},{"id":43,"title":"评审代码","done":true}],"reason":""},"rst_err":""}
AI:vikunja;列出任务 → {"rst_types":"text","rst_data":{"status":"ok","count":2,"total":2,"tasks":[{"id":42,"title":"写周报","done":false},{"id":43,"title":"评审代码","done":true}],"reason":""},"rst_err":""}
AI:vikunja;done,42 → {"rst_types":"text","rst_data":{"status":"ok","id":42,"done":true,"reason":""},"rst_err":""}
AI:vikunja;完成任务,42 → {"rst_types":"text","rst_data":{"status":"ok","id":42,"done":true,"reason":""},"rst_err":""}

# bd-cloud — 百度云服务（需 requests + bd-ocr/bd-qianfan 双凭据）
AI:bd-cloud;ocr,https://example.com/receipt.png → {"rst_types":"text","rst_data":{"status":"ok","count":3,"text":["金额：12.00","商家：示例店","日期：2026-08-12"],"reason":""},"rst_err":""}
AI:百度云;文字识别,https://example.com/receipt.png → {"rst_types":"text","rst_data":{"status":"ok","count":3,"text":["金额：12.00","商家：示例店","日期：2026-08-12"],"reason":""},"rst_err":""}
AI:bd-cloud;baike,秦始皇 → {"rst_types":"text","rst_data":{"status":"ok","lemma_id":"1001","title":"秦始皇","summary":"中国历史上第一位皇帝...","reason":""},"rst_err":""}
AI:百度云;百科,秦始皇 → {"rst_types":"text","rst_data":{"status":"ok","lemma_id":"1001","title":"秦始皇","summary":"中国历史上第一位皇帝...","reason":""},"rst_err":""}
AI:bd-cloud;search,今天有哪些科技新闻 → {"rst_types":"text","rst_data":{"status":"ok","answer":"...","count":5,"sources":[{"title":"...","url":"..."}],"reason":""},"rst_err":""}
AI:百度云;搜索,今天有哪些科技新闻 → {"rst_types":"text","rst_data":{"status":"ok","answer":"...","count":5,"sources":[{"title":"...","url":"..."}],"reason":""},"rst_err":""}

# bd-map — 百度地图（需 bd 凭据）
AI:bd-map;geocode,北京市海淀区中关村 → {"rst_types":"text","rst_data":{"status":"ok","coord_sys":"wgs84","lon":116.31,"lat":39.98,"address":"北京市海淀区中关村","formatted":"...","level":" poi"},"rst_err":""}
AI:百度地图;地理编码,北京市海淀区中关村 → {"rst_types":"text","rst_data":{"status":"ok","coord_sys":"wgs84","lon":116.31,"lat":39.98,"address":"北京市海淀区中关村","formatted":"...","level":" poi"},"rst_err":""}
AI:bd-map;route,北京市朝阳区,北京市海淀区,transit,1 → {"rst_types":"text","rst_data":{"status":"ok","coord_sys":"bd09ll","mode":"transit","distance":12000,"duration":1800,"from":"北京市朝阳区","to":"北京市海淀区","steps":["..."],"reason":""},"rst_err":""}
AI:百度地图;路线规划,北京市朝阳区,北京市海淀区,transit,1 → {"rst_types":"text","rst_data":{"status":"ok","coord_sys":"bd09ll","mode":"transit","distance":12000,"duration":1800,"from":"北京市朝阳区","to":"北京市海淀区","steps":["..."],"reason":""},"rst_err":""}
AI:bd-map;static-map,116.31,39.98,14,400,116.31 39.98|116.40 39.99 → {"rst_types":"text","rst_data":{"status":"ok","coord_sys":"bd09ll","url":"data:image/png;base64,...","center":"116.31,39.98","zoom":14,"size":400,"marker_count":2,"label_count":0,"has_path":false},"rst_err":""}

# gd-map — 高德地图（需 gd 双凭据 + MD5 签名）
AI:gd-map;geocode,北京市朝阳区阜通东大街6号 → {"rst_types":"text","rst_data":{"status":"ok","coord_sys":"gcj02","lon":116.48,"lat":39.99,"address":"北京市朝阳区阜通东大街6号","formatted":"...","level":" 门牌"},"rst_err":""}
AI:高德地图;地理编码,北京市朝阳区阜通东大街6号 → {"rst_types":"text","rst_data":{"status":"ok","coord_sys":"gcj02","lon":116.48,"lat":39.99,"address":"北京市朝阳区阜通东大街6号","formatted":"...","level":" 门牌"},"rst_err":""}
AI:gd-map;reverse-geocode,116.48,39.99,商务写字楼,1000 → {"rst_types":"text","rst_data":{"status":"ok","coord_sys":"gcj02","address":"北京市朝阳区...","pois":[{"name":"某某写字楼","address":"..."}],"reason":""},"rst_err":""}
AI:高德地图;逆地理编码,116.48,39.99,商务写字楼,1000 → {"rst_types":"text","rst_data":{"status":"ok","coord_sys":"gcj02","address":"北京市朝阳区...","pois":[{"name":"某某写字楼","address":"..."}],"reason":""},"rst_err":""}
AI:gd-map;search,餐厅,116.39,39.91;116.41,39.91;116.41,39.93;116.39,39.93 → {"rst_types":"text","rst_data":{"status":"ok","coord_sys":"gcj02","keyword":"餐厅","count":8,"pois":[{"name":"...","address":"..."}],"reason":""},"rst_err":""}
AI:高德地图;搜索,餐厅,116.39,39.91;116.41,39.91;116.41,39.93;116.39,39.93 → {"rst_types":"text","rst_data":{"status":"ok","coord_sys":"gcj02","keyword":"餐厅","count":8,"pois":[{"name":"...","address":"..."}],"reason":""},"rst_err":""}

# tx-map — 腾讯地图（需 tx 双凭据）
AI:tx-map;geocode,威海市环翠区 → {"rst_types":"text","rst_data":{"status":"ok","address":"威海市环翠区","coord_sys":"gcj02","lat":37.50,"lng":122.12,"type":" 街区","reason":""},"rst_err":""}
AI:腾讯地图;地理编码,威海市环翠区 → {"rst_types":"text","rst_data":{"status":"ok","address":"威海市环翠区","coord_sys":"gcj02","lat":37.50,"lng":122.12,"type":" 街区","reason":""},"rst_err":""}
AI:tx-map;route,威海站,威海公园,polyline → {"rst_types":"text","rst_data":{"status":"ok","coord_sys":"wgs84","distance":4500,"duration_min":12,"point_count":20,"polyline":"...","roads":["..."],"reason":""},"rst_err":""}
AI:腾讯地图;路线规划,威海站,威海公园,polyline → {"rst_types":"text","rst_data":{"status":"ok","coord_sys":"wgs84","distance":4500,"duration_min":12,"point_count":20,"polyline":"...","roads":["..."],"reason":""},"rst_err":""}
AI:tx-map;ip,119.190.214.126 → {"rst_types":"text","rst_data":{"status":"ok","city":"威海市","coord_sys":"gcj02","ip":"119.190.214.126","lat":37.50,"lng":122.12,"nation":"中国","province":"山东省","reason":""},"rst_err":""}
AI:腾讯地图;IP定位,119.190.214.126 → {"rst_types":"text","rst_data":{"status":"ok","city":"威海市","coord_sys":"gcj02","ip":"119.190.214.126","lat":37.50,"lng":122.12,"nation":"中国","province":"山东省","reason":""},"rst_err":""}

# zhihu-cloud — 知乎搜索（需 requests + zhihu 凭据）
AI:zhihu-cloud;search,大模型推理优化 → {"rst_types":"text","rst_data":{"status":"ok","count":3,"count_requested":10,"query":"大模型推理优化","source":"zhihu","sources":[{"title":"...","snippet":"...","authority":2,"voteup":128}],"reason":""},"rst_err":""}
AI:知乎搜索;站内搜索,大模型推理优化 → {"rst_types":"text","rst_data":{"status":"ok","count":3,"count_requested":10,"query":"大模型推理优化","source":"zhihu","sources":[{"title":"...","snippet":"...","authority":2,"voteup":128}],"reason":""},"rst_err":""}
AI:zhihu-cloud;global-search,AI 应用案例,5 → {"rst_types":"text","rst_data":{"status":"ok","count":5,"count_requested":5,"query":"AI 应用案例","search_db":"all","source":"zhihu-share","sources":[{"title":"...","url":"...","snippet":"..."}],"reason":""},"rst_err":""}
AI:知乎搜索;全网搜索,AI 应用案例,5 → {"rst_types":"text","rst_data":{"status":"ok","count":5,"count_requested":5,"query":"AI 应用案例","search_db":"all","source":"zhihu-share","sources":[{"title":"...","url":"...","snippet":"..."}],"reason":""},"rst_err":""}
```

> 以上 `rst_data` 字段与各包 `schema.json` 的 `outputs` 对齐；参数为 JSON 的指令，JSON 整体作为一个逗号分隔项传入。完整指令表与参数说明见各包目录 `README_zh.md` / `README.md`。
