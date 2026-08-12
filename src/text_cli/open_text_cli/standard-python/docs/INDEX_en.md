# standard-python Package Index (INDEX_en.md)

> This file is the **package manifest** for the `standard-python/` directory. For per-package installation steps, the instruction table, and usage examples, see each package's own `README_zh.md` (Chinese) and `README.md` (English).

## 1. About This Directory

- **Positioning**: A collection of Python standard-runtime instruction packages. Each package is a ready-to-use basic tool that can be `install`ed on demand.
- **Runtime**: The standard runtime (Python), to be installed and used within the A3+ Service or the A9 full runtime. `web-utils` runs on the Node runtime (deployed as a Tencent CloudBase cloud function).
- **Dependencies**: The `tc-*` base tools have zero external dependencies and use pure stdlib, except `tc-table` (XLSX is optional via openpyxl); `image` (Pillow), `skill-csv2json` (copilot bridge), `ai-inference` (credential injection — vendors/models are injected via config, not hardcoded); map and cloud-service packages (`bd-map`/`gd-map`/`tx-map`/`bd-cloud`/`aria2`/`vikunja`/`zhihu-cloud`) require the `text_cli_modules/key/` runtime module and the corresponding credentials; `web-utils` depends on `wx-server-sdk`.

## 2. Package Manifest

| Package ID | Version | License | Form | External deps | Description |
| --- | --- | --- | --- | --- | --- |
| [`tc-math`](tc-math/) | 0.1.2 | MIT | tool | none | Safe arithmetic evaluator for path pipelines. AST-validated, zero-dependency, uses only the math standard library. |
| [`tc-json`](tc-json/) | 0.1.2 | MIT | tool | none | Pure-stdlib JSON structure primitives: validate, pretty-print, list keys, shallow merge, dot-path resolve. Zero-dependency. |
| [`tc-diff`](tc-diff/) | 0.1.2 | MIT | tool | none | Text diffing tool for path pipelines. Line-level unified diff, similarity ratio, patch apply, word-level diff. Zero external dependency, pure stdlib difflib. |
| [`tc-datetime`](tc-datetime/) | 0.1.1 | MIT | tool | none | Date/time computation tool for path pipelines. now / offset / between / weekday / range / format. Zero external dependency, pure stdlib datetime. |
| [`tc-sql`](tc-sql/) | 0.1.2 | MIT | tool | none | Unified SQL query protocol layer. Routing + auth + execution; any data owner joins by declaration. |
| [`tc-table`](tc-table/) | 0.1.2 | MIT | tool | none (XLSX optional openpyxl) | Tabular data tool for path pipelines. Read CSV/TSV/XLSX → JSON array → filter/sort/pivot/join → write back. |
| [`tc-archive`](tc-archive/) | 0.1.2 | MIT | tool | none | Archive/compression tool for path pipelines. Create, extract, list archives (zip/tar/tar.gz/tar.bz2/tar.xz). Zero external dependency, pure stdlib zipfile + tarfile. Path allowlist + zip-bomb defense. |
| [`tc-markdown`](tc-markdown/) | 0.1.2 | MIT | tool | none | Read and parse Markdown files: extract full text, heading structure, content under a given heading. Restricted path access for safety. |
| [`path-str`](path-str/) | 0.1.1 | MIT | tool | none | String base operations for path pipeline composition: template substitution, split, join. Zero-dependency, standard library only. |
| [`weather`](weather/) | 0.1.1 | MIT | tool | none | Query weather forecast by city and date. Open-Meteo / wttr.in dual keyless fallback sources; `lang` controls output language (zh / en / ja). |
| [`image`](image/) | 0.1.2 | MIT | tool | Pillow | Image info read, base64 encode, format conversion and resize (based on Pillow). |
| [`skill-csv2json`](skill-csv2json/) | 0.1.1 | MIT | tool | modules (handlers/skill_bridge) | Convert CSV files to JSON arrays via the ClawHub csv2json skill. Delegated to the copilot Skill Bridge generic adapter for execution. |
| [`ai-inference`](ai-inference/) | 0.1.2 | MIT | tool | credentials (ai_api_key) | Text inference and vision analysis based on a configurable AI vendor. **Mechanism only** — no specific vendor / model / endpoint is built in; vendor name and model are both configured in `config/model_aliases.json`, not hardcoded, and injected at runtime via `init_ai_handler()` / `set_model_registry()`. |
| [`aria2`](aria2/) | 0.1.1 | MIT | tool | requests + key module | Manage download tasks via the aria2 JSON-RPC API. Add HTTP/BT downloads, query progress, control tasks. |
| [`vikunja`](vikunja/) | 0.1.1 | MIT | tool | requests + key module | Manage self-hosted tasks via the Vikunja API. Create, update, complete tasks; organize into projects; use tags; manage task relations for path-pipeline routing. |
| [`bd-cloud`](bd-cloud/) | 0.1.1 | MIT | tool | requests + key module | Baidu Cloud API wrapper: OCR, encyclopedia lookup, AI web search, async video notes. Dual-credential auth (bd-ocr + bd-qianfan). |
| [`bd-map`](bd-map/) | 0.1.1 | MIT | tool | key module | Baidu Maps HTTP API wrapper: geocoding, IP location, route planning (driving/bus/walking/cycling), coordinate conversion, static map (markers/labels/polyline overlays). |
| [`gd-map`](gd-map/) | 0.1.1 | MIT | tool | key module | Amap (Gaode) HTTP API wrapper: geocoding, reverse geocoding (incl. nearby POIs), static map (markers/polyline overlays), polygon POI search. Dual-credential + MD5 signature auth. |
| [`tx-map`](tx-map/) | 0.1.1 | MIT | tool | key module | Tencent Maps HTTP API wrapper: geocoding, reverse geocoding, route planning, static map, IP location. Dual-credential auth + quota tracking. |
| [`zhihu-cloud`](zhihu-cloud/) | 0.1.1 | MIT | tool | requests + key module | Search Zhihu on-site content and the web-wide index via the Zhihu Open Platform API. |

## 3. Versioning and License Notes

- **Version scheme**: Uses Semver version subdirectories (`V0_1_1` / `V0_1_2`); one directory per version under each package root, with the latest version directory being that package's current mirror. Initial release is uniformly `0.1.1`; some packages have iterated to `0.1.2`.
- **MIT license**: This collection uniformly adopts the MIT license — free to use, modify, and redistribute, provided the copyright and license notices are retained.
- **Content source**: Each package here is a clean copy of the corresponding artifact under `text-cli-package/releases/` (privacy data stripped). Only comments and docs are kept; `DESIGN.md` / `.dev` / test scripts are excluded.

## 4. Instruction Examples

After installing any package, send a text instruction prefixed with `AI:` to the runtime to invoke it. Instruction format `AI:domain;action,<args...>`; `domain`/`action` may use the `_zh` Chinese aliases declared in each package's `schema.json` (e.g. `AI:计算;求值,2+3*4`). The dict returned by the handler is used directly as the `rst_data` field of the response envelope. Below, representative instructions and responses are given in package-manifest order; under each English instruction is the equivalent Chinese-alias form:

```
# tc-math — safe arithmetic evaluation
AI:tc-math;eval,2+3*4 → {"rst_types":"text","rst_data":{"status":"ok","result":14},"rst_err":""}
AI:计算;求值,2+3*4 → {"rst_types":"text","rst_data":{"status":"ok","result":14},"rst_err":""}   # zh alias
AI:tc-math;eval,sqrt(3**2+4**2) → {"rst_types":"text","rst_data":{"status":"ok","result":5.0},"rst_err":""}
AI:计算;求值,sqrt(3**2+4**2) → {"rst_types":"text","rst_data":{"status":"ok","result":5.0},"rst_err":""}   # zh alias

# tc-json — structure primitives
AI:tc-json;parse,{"name":"text-cli"} → {"rst_types":"text","rst_data":{"status":"ok","result":{"name":"text-cli"}},"rst_err":""}
AI:tc-json;解析,{"name":"text-cli"} → {"rst_types":"text","rst_data":{"status":"ok","result":{"name":"text-cli"}},"rst_err":""}   # zh alias
AI:tc-json;validate,'{"a":1}' → {"rst_types":"text","rst_data":{"status":"ok","valid":true},"rst_err":""}
AI:tc-json;校验,'{"a":1}' → {"rst_types":"text","rst_data":{"status":"ok","valid":true},"rst_err":""}   # zh alias

# tc-diff — text diffing
AI:tc-diff;similarity,hello world,hello there → {"rst_types":"text","rst_data":{"status":"ok","similarity":0.53},"rst_err":""}
AI:文本差异;相似度,hello world,hello there → {"rst_types":"text","rst_data":{"status":"ok","similarity":0.53},"rst_err":""}   # zh alias
AI:tc-diff;unified,line a,line b → {"rst_types":"text","rst_data":{"status":"ok","has_diff":true,"similarity":0.0},"rst_err":""}
AI:文本差异;统一差异,line a,line b → {"rst_types":"text","rst_data":{"status":"ok","has_diff":true,"similarity":0.0},"rst_err":""}   # zh alias

# tc-datetime — date/time
AI:tc-datetime;now → {"rst_types":"text","rst_data":{"status":"ok","date":"2026-08-12T09:30:00","timezone":"UTC"},"rst_err":""}
AI:日期时间;现在 → {"rst_types":"text","rst_data":{"status":"ok","date":"2026-08-12T09:30:00","timezone":"UTC"},"rst_err":""}   # zh alias
AI:tc-datetime;between,2026-01-01,2026-01-31,days → {"rst_types":"text","rst_data":{"status":"ok","result":30},"rst_err":""}
AI:日期时间;间距,2026-01-01,2026-01-31,days → {"rst_types":"text","rst_data":{"status":"ok","result":30},"rst_err":""}   # zh alias

# tc-sql — unified SQL protocol layer
AI:tc-sql;tables,main → {"rst_types":"text","rst_data":{"status":"ok","reason":["users","orders"]},"rst_err":""}
AI:SQL查询;表列表,main → {"rst_types":"text","rst_data":{"status":"ok","reason":["users","orders"]},"rst_err":""}   # zh alias
AI:tc-sql;query,main,{"table":"users","columns":["id","name"],"limit":10} → {"rst_types":"text","rst_data":{"status":"ok","reason":[{"id":1,"name":"text-cli"}]},"rst_err":""}
AI:SQL查询;查询,main,{"table":"users","columns":["id","name"],"limit":10} → {"rst_types":"text","rst_data":{"status":"ok","reason":[{"id":1,"name":"text-cli"}]},"rst_err":""}   # zh alias

# tc-table — tabular processing
AI:tc-table;read,data.csv → {"rst_types":"text","rst_data":{"status":"ok","columns":["name","age"],"row_count":2,"rows":[{"name":"a","age":1},{"name":"b","age":2}]},"rst_err":""}
AI:表格;读取,data.csv → {"rst_types":"text","rst_data":{"status":"ok","columns":["name","age"],"row_count":2,"rows":[{"name":"a","age":1},{"name":"b","age":2}]},"rst_err":""}   # zh alias
AI:tc-table;filter,[{"name":"a","age":1},{"name":"b","age":2}],{"where":["age",">",1]} → {"rst_types":"text","rst_data":{"status":"ok","rows":[{"name":"b","age":2}],"count":1,"filtered_count":1},"rst_err":""}
AI:表格;筛选,[{"name":"a","age":1},{"name":"b","age":2}],{"where":["age",">",1]} → {"rst_types":"text","rst_data":{"status":"ok","rows":[{"name":"b","age":2}],"count":1,"filtered_count":1},"rst_err":""}   # zh alias

# tc-archive — archive/compression
AI:tc-archive;create,out.zip,data → {"rst_types":"text","rst_data":{"status":"ok","path":"out.zip","entries":["data/a.txt"],"count":1},"rst_err":""}
AI:压缩归档;创建归档,out.zip,data → {"rst_types":"text","rst_data":{"status":"ok","path":"out.zip","entries":["data/a.txt"],"count":1},"rst_err":""}   # zh alias
AI:tc-archive;extract,out.zip,dist → {"rst_types":"text","rst_data":{"status":"ok","path":"dist","entries":["data/a.txt"],"count":1},"rst_err":""}
AI:压缩归档;解压归档,out.zip,dist → {"rst_types":"text","rst_data":{"status":"ok","path":"dist","entries":["data/a.txt"],"count":1},"rst_err":""}   # zh alias
AI:tc-archive;list,out.zip → {"rst_types":"text","rst_data":{"status":"ok","entries":["data/a.txt"],"count":1},"rst_err":""}
AI:压缩归档;列出内容,out.zip → {"rst_types":"text","rst_data":{"status":"ok","entries":["data/a.txt"],"count":1},"rst_err":""}   # zh alias

# tc-markdown — Markdown read
AI:tc-markdown;read,doc.md → {"rst_types":"text","rst_data":{"status":"ok","reason":"# Title\ncontent"},"rst_err":""}
AI:tc-markdown;读取,doc.md → {"rst_types":"text","rst_data":{"status":"ok","reason":"# Title\ncontent"},"rst_err":""}   # zh alias
AI:tc-markdown;headings,doc.md → {"rst_types":"text","rst_data":{"status":"ok","reason":[{"level":1,"text":"Title","line":1}]},"rst_err":""}
AI:tc-markdown;标题,doc.md → {"rst_types":"text","rst_data":{"status":"ok","reason":[{"level":1,"text":"Title","line":1}]},"rst_err":""}   # zh alias
AI:tc-markdown;section,doc.md,Intro → {"rst_types":"text","rst_data":{"status":"ok","reason":"intro body"},"rst_err":""}
AI:tc-markdown;章节,doc.md,Intro → {"rst_types":"text","rst_data":{"status":"ok","reason":"intro body"},"rst_err":""}   # zh alias

# path-str — path strings
AI:path-str;template,{base}/out/{0},base=/tmp,0=file → {"rst_types":"text","rst_data":{"status":"ok","result":"/tmp/out/file"},"rst_err":""}
AI:路径字符串;模板,{base}/out/{0},base=/tmp,0=file → {"rst_types":"text","rst_data":{"status":"ok","result":"/tmp/out/file"},"rst_err":""}   # zh alias
AI:path-str;split,'a/b/c','/' → {"rst_types":"text","rst_data":{"status":"ok","parts":["a","b","c"],"count":3},"rst_err":""}
AI:路径字符串;切分,'a/b/c','/' → {"rst_types":"text","rst_data":{"status":"ok","parts":["a","b","c"],"count":3},"rst_err":""}   # zh alias
AI:path-str;join,'["a","b","c"]','/' → {"rst_types":"text","rst_data":{"status":"ok","result":"a/b/c"},"rst_err":""}
AI:路径字符串;合并,'["a","b","c"]','/' → {"rst_types":"text","rst_data":{"status":"ok","result":"a/b/c"},"rst_err":""}   # zh alias

# weather — weather query (keyless dual-source fallback)
AI:weather;query,Weihai → {"rst_types":"text","rst_data":{"status":"ok","source":"open-meteo","city":"Weihai","date":"2026-08-12","temp_min":24,"temp_max":30,"weather_desc":"Clear","lang":"en"},"rst_err":""}
AI:天气;查询,威海 → {"rst_types":"text","rst_data":{"status":"ok","source":"open-meteo","city":"威海","date":"2026-08-12","temp_min":24,"temp_max":30,"weather_desc":"晴","lang":"zh"},"rst_err":""}   # zh alias

# image — image processing (requires Pillow)
AI:image;info,photo.png,json → {"rst_types":"text","rst_data":{"status":"ok","width":1920,"height":1080,"format":"PNG","size_bytes":123456,"mode":"RGB","frames":1,"result":"photo.png"},"rst_err":""}
AI:图片;信息,photo.png,json → {"rst_types":"text","rst_data":{"status":"ok","width":1920,"height":1080,"format":"PNG","size_bytes":123456,"mode":"RGB","frames":1,"result":"photo.png"},"rst_err":""}   # zh alias
AI:image;encode,photo.png → {"rst_types":"text","rst_data":{"status":"ok","cache_key":"cache://img/abc","original":"photo.png","encoded":"base64...","expires_seconds":3600,"result":"cache://img/abc"},"rst_err":""}
AI:图片;编码,photo.png → {"rst_types":"text","rst_data":{"status":"ok","cache_key":"cache://img/abc","original":"photo.png","encoded":"base64...","expires_seconds":3600,"result":"cache://img/abc"},"rst_err":""}   # zh alias
AI:image;convert,in.png,jpg → {"rst_types":"text","rst_data":{"status":"ok","path":"out.jpg","width":1920,"height":1080,"format":"JPEG","result":"out.jpg"},"rst_err":""}
AI:图片;转换,in.png,jpg → {"rst_types":"text","rst_data":{"status":"ok","path":"out.jpg","width":1920,"height":1080,"format":"JPEG","result":"out.jpg"},"rst_err":""}   # zh alias
AI:image;resize,in.png,800,600 → {"rst_types":"text","rst_data":{"status":"ok","path":"out.png","width":800,"height":600,"original_width":1920,"original_height":1080,"result":"out.png"},"rst_err":""}
AI:图片;缩放,in.png,800,600 → {"rst_types":"text","rst_data":{"status":"ok","path":"out.png","width":800,"height":600,"original_width":1920,"original_height":1080,"result":"out.png"},"rst_err":""}   # zh alias

# ai-inference — AI inference (mechanism only; vendor injected via config)
AI:ai-inference;infer,What is the capital of France?,auto → {"rst_types":"text","rst_data":{"status":"ok","result":"The capital of France is Paris."},"rst_err":""}
AI:AI推理;推理,法国的首都是哪里?,auto → {"rst_types":"text","rst_data":{"status":"ok","result":"法国的首都是巴黎。"},"rst_err":""}   # zh alias
AI:ai-inference;vision,Describe this image,https://example.com/photo.jpg,quality → {"rst_types":"text","rst_data":{"status":"ok","result":"The image shows a sunset over mountains..."},"rst_err":""}
AI:AI推理;视觉,描述这张图片,https://example.com/photo.jpg,quality → {"rst_types":"text","rst_data":{"status":"ok","result":"图片显示山脉上方的日落..."},"rst_err":""}   # zh alias
AI:ai-inference;infer,Summarize the key points,cache:abc123 → {"rst_types":"text","rst_data":{"status":"ok","result":"...","cache_key":"def456"},"rst_err":""}
AI:AI推理;推理,总结要点,cache:abc123 → {"rst_types":"text","rst_data":{"status":"ok","result":"...","cache_key":"def456"},"rst_err":""}   # zh alias

# skill-csv2json — CSV to JSON (copilot bridge)
AI:skill-csv2json;convert,data.csv → {"rst_types":"text","rst_data":{"status":"ok","data":[{"name":"a","age":1},{"name":"b","age":2}],"count":2},"rst_err":""}
AI:skill-csv2json;转换,data.csv → {"rst_types":"text","rst_data":{"status":"ok","data":[{"name":"a","age":1},{"name":"b","age":2}],"count":2},"rst_err":""}   # zh alias

# aria2 — download management (requires requests + aria2 credentials)
AI:aria2;add-uri,{"uris":["https://example.com/a.zip"],"options":{"out":"a.zip"}} → {"rst_types":"text","rst_data":{"status":"ok","gid":"d7c...","reason":"added"},"rst_err":""}
AI:aria2;添加下载,{"uris":["https://example.com/a.zip"],"options":{"out":"a.zip"}} → {"rst_types":"text","rst_data":{"status":"ok","gid":"d7c...","reason":"added"},"rst_err":""}   # zh alias
AI:aria2;status,d7c1e2f3 → {"rst_types":"text","rst_data":{"status":"ok","gid":"d7c1e2f3","reason":{"state":"active","progress":0.42,"speed":102400}},"rst_err":""}
AI:aria2;下载状态,d7c1e2f3 → {"rst_types":"text","rst_data":{"status":"ok","gid":"d7c1e2f3","reason":{"state":"active","progress":0.42,"speed":102400}},"rst_err":""}   # zh alias
AI:aria2;active → {"rst_types":"text","rst_data":{"status":"ok","count":2,"downloads":[{"gid":"d7c...","progress":0.42},{"gid":"a1b...","progress":0.10}],"reason":""},"rst_err":""}
AI:aria2;global-stat → {"rst_types":"text","rst_data":{"status":"ok","download_speed":102400,"upload_speed":0,"num_active":2,"num_waiting":0,"num_stopped":5,"reason":""},"rst_err":""}

# vikunja — task management (requires requests + vikunja credentials)
AI:vikunja;create-task,{"title":"Write weekly report","priority":3,"due_date":"2026-08-15"} → {"rst_types":"text","rst_data":{"status":"ok","id":42,"title":"Write weekly report","priority":3,"done":false,"due_date":"2026-08-15","reason":""},"rst_err":""}
AI:vikunja;创建任务,{"title":"写周报","priority":3,"due_date":"2026-08-15"} → {"rst_types":"text","rst_data":{"status":"ok","id":42,"title":"写周报","priority":3,"done":false,"due_date":"2026-08-15","reason":""},"rst_err":""}   # zh alias
AI:vikunja;list-tasks → {"rst_types":"text","rst_data":{"status":"ok","count":2,"total":2,"tasks":[{"id":42,"title":"Write weekly report","done":false},{"id":43,"title":"Review code","done":true}],"reason":""},"rst_err":""}
AI:vikunja;列出任务 → {"rst_types":"text","rst_data":{"status":"ok","count":2,"total":2,"tasks":[{"id":42,"title":"写周报","done":false},{"id":43,"title":"评审代码","done":true}],"reason":""},"rst_err":""}   # zh alias
AI:vikunja;done,42 → {"rst_types":"text","rst_data":{"status":"ok","id":42,"done":true,"reason":""},"rst_err":""}
AI:vikunja;完成任务,42 → {"rst_types":"text","rst_data":{"status":"ok","id":42,"done":true,"reason":""},"rst_err":""}   # zh alias

# bd-cloud — Baidu Cloud services (requires requests + bd-ocr/bd-qianfan dual credentials)
AI:bd-cloud;ocr,https://example.com/receipt.png → {"rst_types":"text","rst_data":{"status":"ok","count":3,"text":["Amount: 12.00","Merchant: Example Store","Date: 2026-08-12"],"reason":""},"rst_err":""}
AI:百度云;文字识别,https://example.com/receipt.png → {"rst_types":"text","rst_data":{"status":"ok","count":3,"text":["金额：12.00","商家：示例店","日期：2026-08-12"],"reason":""},"rst_err":""}   # zh alias
AI:bd-cloud;baike,Qin Shi Huang → {"rst_types":"text","rst_data":{"status":"ok","lemma_id":"1001","title":"Qin Shi Huang","summary":"The first emperor in Chinese history...","reason":""},"rst_err":""}
AI:百度云;百科,秦始皇 → {"rst_types":"text","rst_data":{"status":"ok","lemma_id":"1001","title":"秦始皇","summary":"中国历史上第一位皇帝...","reason":""},"rst_err":""}   # zh alias
AI:bd-cloud;search,What tech news is there today → {"rst_types":"text","rst_data":{"status":"ok","answer":"...","count":5,"sources":[{"title":"...","url":"..."}],"reason":""},"rst_err":""}
AI:百度云;搜索,今天有哪些科技新闻 → {"rst_types":"text","rst_data":{"status":"ok","answer":"...","count":5,"sources":[{"title":"...","url":"..."}],"reason":""},"rst_err":""}   # zh alias

# bd-map — Baidu Maps (requires bd credentials)
AI:bd-map;geocode,北京市海淀区中关村 → {"rst_types":"text","rst_data":{"status":"ok","coord_sys":"wgs84","lon":116.31,"lat":39.98,"address":"北京市海淀区中关村","formatted":"...","level":" poi"},"rst_err":""}
AI:百度地图;地理编码,北京市海淀区中关村 → {"rst_types":"text","rst_data":{"status":"ok","coord_sys":"wgs84","lon":116.31,"lat":39.98,"address":"北京市海淀区中关村","formatted":"...","level":" poi"},"rst_err":""}   # zh alias
AI:bd-map;route,北京市朝阳区,北京市海淀区,transit,1 → {"rst_types":"text","rst_data":{"status":"ok","coord_sys":"bd09ll","mode":"transit","distance":12000,"duration":1800,"from":"北京市朝阳区","to":"北京市海淀区","steps":["..."],"reason":""},"rst_err":""}
AI:百度地图;路线规划,北京市朝阳区,北京市海淀区,transit,1 → {"rst_types":"text","rst_data":{"status":"ok","coord_sys":"bd09ll","mode":"transit","distance":12000,"duration":1800,"from":"北京市朝阳区","to":"北京市海淀区","steps":["..."],"reason":""},"rst_err":""}   # zh alias
AI:bd-map;static-map,116.31,39.98,14,400,116.31 39.98|116.40 39.99 → {"rst_types":"text","rst_data":{"status":"ok","coord_sys":"bd09ll","url":"data:image/png;base64,...","center":"116.31,39.98","zoom":14,"size":400,"marker_count":2,"label_count":0,"has_path":false},"rst_err":""}

# gd-map — Amap / Gaode (requires gd dual credentials + MD5 signature)
AI:gd-map;geocode,北京市朝阳区阜通东大街6号 → {"rst_types":"text","rst_data":{"status":"ok","coord_sys":"gcj02","lon":116.48,"lat":39.99,"address":"北京市朝阳区阜通东大街6号","formatted":"...","level":" 门牌"},"rst_err":""}
AI:高德地图;地理编码,北京市朝阳区阜通东大街6号 → {"rst_types":"text","rst_data":{"status":"ok","coord_sys":"gcj02","lon":116.48,"lat":39.99,"address":"北京市朝阳区阜通东大街6号","formatted":"...","level":" 门牌"},"rst_err":""}   # zh alias
AI:gd-map;reverse-geocode,116.48,39.99,商务写字楼,1000 → {"rst_types":"text","rst_data":{"status":"ok","coord_sys":"gcj02","address":"北京市朝阳区...","pois":[{"name":"Some Office Building","address":"..."}],"reason":""},"rst_err":""}
AI:高德地图;逆地理编码,116.48,39.99,商务写字楼,1000 → {"rst_types":"text","rst_data":{"status":"ok","coord_sys":"gcj02","address":"北京市朝阳区...","pois":[{"name":"某某写字楼","address":"..."}],"reason":""},"rst_err":""}   # zh alias
AI:gd-map;search,餐厅,116.39,39.91;116.41,39.91;116.41,39.93;116.39,39.93 → {"rst_types":"text","rst_data":{"status":"ok","coord_sys":"gcj02","keyword":"餐厅","count":8,"pois":[{"name":"...","address":"..."}],"reason":""},"rst_err":""}
AI:高德地图;搜索,餐厅,116.39,39.91;116.41,39.91;116.41,39.93;116.39,39.93 → {"rst_types":"text","rst_data":{"status":"ok","coord_sys":"gcj02","keyword":"餐厅","count":8,"pois":[{"name":"...","address":"..."}],"reason":""},"rst_err":""}   # zh alias

# tx-map — Tencent Maps (requires tx dual credentials)
AI:tx-map;geocode,威海市环翠区 → {"rst_types":"text","rst_data":{"status":"ok","address":"威海市环翠区","coord_sys":"gcj02","lat":37.50,"lng":122.12,"type":" 街区","reason":""},"rst_err":""}
AI:腾讯地图;地理编码,威海市环翠区 → {"rst_types":"text","rst_data":{"status":"ok","address":"威海市环翠区","coord_sys":"gcj02","lat":37.50,"lng":122.12,"type":" 街区","reason":""},"rst_err":""}   # zh alias
AI:tx-map;route,威海站,威海公园,polyline → {"rst_types":"text","rst_data":{"status":"ok","coord_sys":"wgs84","distance":4500,"duration_min":12,"point_count":20,"polyline":"...","roads":["..."],"reason":""},"rst_err":""}
AI:腾讯地图;路线规划,威海站,威海公园,polyline → {"rst_types":"text","rst_data":{"status":"ok","coord_sys":"wgs84","distance":4500,"duration_min":12,"point_count":20,"polyline":"...","roads":["..."],"reason":""},"rst_err":""}   # zh alias
AI:tx-map;ip,119.190.214.126 → {"rst_types":"text","rst_data":{"status":"ok","city":"威海市","coord_sys":"gcj02","ip":"119.190.214.126","lat":37.50,"lng":122.12,"nation":"中国","province":"山东省","reason":""},"rst_err":""}
AI:腾讯地图;IP定位,119.190.214.126 → {"rst_types":"text","rst_data":{"status":"ok","city":"威海市","coord_sys":"gcj02","ip":"119.190.214.126","lat":37.50,"lng":122.12,"nation":"中国","province":"山东省","reason":""},"rst_err":""}   # zh alias

# zhihu-cloud — Zhihu search (requires requests + zhihu credentials)
AI:zhihu-cloud;search,LLM inference optimization → {"rst_types":"text","rst_data":{"status":"ok","count":3,"count_requested":10,"query":"LLM inference optimization","source":"zhihu","sources":[{"title":"...","snippet":"...","authority":2,"voteup":128}],"reason":""},"rst_err":""}
AI:知乎搜索;站内搜索,大模型推理优化 → {"rst_types":"text","rst_data":{"status":"ok","count":3,"count_requested":10,"query":"大模型推理优化","source":"zhihu","sources":[{"title":"...","snippet":"...","authority":2,"voteup":128}],"reason":""},"rst_err":""}   # zh alias
AI:zhihu-cloud;global-search,AI application cases,5 → {"rst_types":"text","rst_data":{"status":"ok","count":5,"count_requested":5,"query":"AI application cases","search_db":"all","source":"zhihu-share","sources":[{"title":"...","url":"...","snippet":"..."}],"reason":""},"rst_err":""}
AI:知乎搜索;全网搜索,AI 应用案例,5 → {"rst_types":"text","rst_data":{"status":"ok","count":5,"count_requested":5,"query":"AI 应用案例","search_db":"all","source":"zhihu-share","sources":[{"title":"...","url":"...","snippet":"..."}],"reason":""},"rst_err":""}   # zh alias
```

> The `rst_data` fields above align with each package's `schema.json` `outputs`. For instructions whose argument is JSON, the whole JSON is passed as a single comma-separated item. See each package's `README_zh.md` / `README.md` for the full instruction table and parameter descriptions.
