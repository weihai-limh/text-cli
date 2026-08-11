# 渐进式部署：真源 → 产物 → 分发

text-cli 的部署链分两段：**真源到产物**（`src/skeleton/` → `deploy/`）和**产物到多平台分发**（`deploy/` → 分发到 Win/Linux/Docker 的制品）。本文档详细说明每一段的机制、约定和设计意图，让"为什么某个文件应该在这里"一目了然。

---

## 1. 真源 → deploy/ 产物

### 1.1 真源在哪

```
src/skeleton/
├── base/                    # A0/A1 — 协议规范 + Agent Skill 定义
│   ├── A0-protocol/         #   直通模式
│   └── A1-skill/            #   依赖模式（以 A0 为依赖，构建时先拷贝 A0 再覆盖 A1）
├── copilot/                 # A2 — 本地 AI 调度（copilot 运行时）
│   └── A2-copilot/
│       └── copilot/         # ← 注意：内层同名子目录是约定的关键
├── service/                 # A3–A9 — service 运行时累积链
│   ├── A3-service/          #   基础平台（安装/卸载/dispatch/代理）
│   ├── A4-paths/            #   + 路径编排引擎
│   ├── A6-sql/              #   + SQLite 持久层
│   ├── A7-mcp/              #   + MCP 双向桥
│   ├── A8-discovery/        #   + 聚合发现入口
│   └── A9-advanced/         #   + 门面抽象
│       └── service/         # ← 每层仅含该层引入的新文件，其余由累积继承
├── endpoint/                # A5 — 集成端点网关（直通同步）
│   └── A5-endpoint/
│       ├── python/          #   FastAPI 变体
│       └── js/              #   Cloudflare Workers 变体（预留）
└── bypass-service/          # BYPASS — 非 Python 云函数（直通同步）
```

**核心规则**：`src/skeleton/` 是唯一的编辑入口。`deploy/` 下任何文件都**不应手动修改**——它由构建脚本从真源生成。

### 1.2 build-all.py：结构透传器

`scripts/build-all.py` 是整个链路的核心。它的关键行为：

```text
collect_source(layer_path)
  └── os.walk(src/skeleton/{layer_path})
       └── 保留源的相对目录结构 ← 这是最关键的不变量
       └── 过滤 SKELETON_SUBDIRS 白名单外的顶层目录
       └── 过滤 _EXCLUDED_FILES 中的开发文件
  → 返回 { 相对路径 → 源文件绝对路径 }
```

这意味着：**源里有什么结构，产物里就有什么结构**。脚本不主动造层、不主动丢层。

### 1.3 三类构建模式

| 模式 | 层 | 行为 |
|------|-----|------|
| **累积** (`build_layer`) | A2–A9 | 逐层叠加，后层覆盖前层同名文件。A3 包含 A2 的全部，A9 包含 A2–A8 的全部 |
| **直通** (`build_through_layer`) | A0/A5/BYPASS | 源码原样镜像到 `deploy/`，不参与累积 |
| **依赖** (`build_dependent_layer`) | A1 | 先拷贝依赖层（A0-protocol），再拷贝主层（A1-skill）。主层覆盖依赖层冲突文件。`deploy/A1-skill/ = A0 SDK + A1 基础设施` |

**累积模型的工程含义**：后层覆盖前层意味着——如果 A3 修了一个 bug 而 A4 持有旧副本，A3 的修复在最终产物中被 A4 覆盖、丢失。**设计约定：一个文件只应在它首次出现的层中持有——后续层通过累积继承，不应持有同名副本。** 违反此约定会导致"腐败副本"：同名文件在不同层各自演化，修复只在一层生效，被后层覆盖后消失。真实案例：`text_cli_install.py` 曾六层各有一份，A3 的 hot-reload 修复被 A4–A9 旧副本覆盖——`find` 交叉比对后统一移除多余副本，A3 一份即可。详见 §4 追踪示例。

### 1.4 SKELETON_SUBDIRS 白名单

```python
SKELETON_SUBDIRS = {"service", "copilot", "media", "MCPservice",
                    "aggregate", "other", "handlers", "packages", "config"}
```

只有这些顶层子目录会被 `os.walk` 纳入复制范围。如果在源中新增了运行时子目录，必须加入此白名单。

### 1.5 开发文件过滤

```python
_EXCLUDED_FILES = frozenset({".gitkeep", ".gitignore", "pytest.ini"})
```

这些文件在源码中有存在理由（git 空目录占位、测试配置），但不应出现在 deploy 产物和最终分发制品中。过滤在 `collect_source()` 和 `build_through_layer()` 两个入口同时生效，确保累积层和直通层都不会带入。

**被保留的目录**：`media/` 等运行时需要的空目录——过滤的是其中的 `.gitkeep` 占位文件，目录本身不会被删除。

### 1.6 产出物映射

```text
src/skeleton/copilot/A2-copilot/copilot/   →   deploy/A2-copilot/copilot/
src/skeleton/service/A3-service/service/   →   deploy/A3-service/service/
       (A2 累积层也落入)                    →   deploy/A3-service/copilot/
src/skeleton/service/A9-advanced/service/  →   deploy/A9-advanced/service/
       (A2–A8 全部累积)                    →   deploy/A9-advanced/copilot/
                                           →   deploy/A9-advanced/MCPservice/
                                           →   deploy/A9-advanced/aggregate/
```

---

## 2. deploy/ 产物 → 多平台分发

`deploy/` 是中间产物——它不是最终交付物。最终交付物由三套分发脚本从 `deploy/` 组装。每层 `deploy/` 目录都是自包含的完整运行时，分发脚本只需整目录拷贝，不挑拣子目录。

### 2.1 分发全景图

```text
                        ┌─────────────────┐
                        │   deploy/        │
                        │   (中间产物)      │
                        └───┬───┬───┬─────┘
                            │   │   │
          ┌─────────────────┘   │   └──────────────────┐
          ▼                     ▼                      ▼
┌─────────────────┐  ┌─────────────────┐  ┌──────────────────────┐
│ scripts/release/ │  │ scripts/release/ │  │ scripts/release/     │
│ win/build.py     │  │ ubuntu/build.py  │  │ container/build.py   │
│ build-endpoint.py│  │ build-endpoint.py│  │                      │
└────────┬────────┘  └────────┬────────┘  └──────────┬───────────┘
         ▼                    ▼                      ▼
  deploy/skeleton-win/  deploy/skeleton-linux/  deploy/skeleton-container/
  .zip                  .tar.gz                 .build/copilot/
                                                .build/service/
                                                .build/advanced/
                                                .build/a5-endpoint/
```

### 2.2 主构建脚本：build.py

每层 `deploy/` 目录是自包含运行时——脚本整目录拷贝，不区分 service/copilot 来源。通过 `--layer` 参数选择目标层，产物命名包含层标识。

```text
scripts/release/{win,ubuntu}/build.py --layer A9
  ┌── _copy_runtime(): deploy/A9-advanced/  →  output/  (full self-contained runtime)
  ├── _copy_docs():    docs/product_manuals/ →  output/docs/
  ├── _copy_packages(): deploy/packages/standard-python/  →  output_parent/packages/
  ├── _copy_protocol(): deploy/A0-protocol/  →  output_parent/protocol/
  ├── _generate_start_{bat,sh}()  (A2=copilot-only, A3+=copilot+service+health-check)
  ├── _clean_descriptors(__pycache__)
  └── _package_zip/tar()
```

**支持的层**：A2, A3, A4, A6, A7, A8, A9。默认 `--layer A9`。A5 不在此脚本范围内（由 build-endpoint.py 处理）。

**产物命名**：

| 平台 | 制品 |
|------|------|
| Win | `deploy/skeleton-win/text-cli-A{layer}-v{version_dir}.zip` |
| Linux | `deploy/skeleton-linux/text-cli-A{layer}-v{version_dir}.tar.gz` |

版本号中的点号替换为下划线：`0.1.1` → `0_1_1`。示例：`text-cli-A9-v0_1_1.zip`。

**两遍执行**：如果同名产物目录已存在，第一遍尝试删除后退出；第二遍在干净目录上完整构建。这是为 safe-delete 等环境限制设计的防御机制。

**依赖的 deploy/ 路径**：

| 脚本 | 读取路径 | 用途 |
|------|---------|------|
| win/ubuntu `build.py` | `deploy/{layer_dir}/` | 自包含运行时 |
| win/ubuntu `build.py` | `docs/product_manuals/` | 分发包文档 |
| win/ubuntu `build.py` | `deploy/packages/standard-python/` | 指令包源（仅 Python 包，与 runtime 同级捆绑）。注意：`build-all.py A9` 只同步 skeleton 层，不触发 `build_packages()`。修改标准包 `src/text_cli/open_text_cli/standard-python/` 后需单独执行 `build-all.py packages` 同步到 deploy |
| win/ubuntu `build.py` | `deploy/A0-protocol/` | 协议消费 SDK（与 runtime 同级捆绑） |

### 2.3 Endpoint 构建脚本：build-endpoint.py

A5 endpoint 不支持 `--layer`——它是一个直通网关，使用 `--variant` 区分平台变体。

```text
scripts/release/{win,ubuntu}/build-endpoint.py --variant python
  ┌── _copy_runtime(): deploy/A5-endpoint/python/  →  output/
  ├── _copy_docs():    docs/product_manuals/        →  output/docs/
  ├── _copy_protocol(): deploy/A0-protocol/         →  output_parent/protocol/
  ├── _generate_start_endpoint_{bat,sh}()  (uvicorn :29050)
  ├── _clean_descriptors(__pycache__)
  └── _package_zip/tar()
```

**变体架构**（为 js 预留钩子）：

```python
VARIANT_MAP = {
    "python": "deploy/A5-endpoint/python",
    # "js": "deploy/A5-endpoint/js",   # TODO: Cloudflare Workers
}
```

python 变体已完整实现。js 变体在 `_generate_start_*()` 和 `_clean_descriptors()` 中有分支桩位，取消 `VARIANT_MAP` 注释后 `--variant js` 自动可用。

**产物命名**：`text-cli-endpoint-{variant}-v{version_dir}.zip`。示例：`text-cli-endpoint-python-v0_1_1.zip`。

### 2.4 容器镜像

`scripts/release/container/build.py` 装配四个 Docker 构建上下文：

```text
scripts/release/container/build.py

  build_copilot():   deploy/A2-copilot/copilot/     → .build/copilot/    [+ A2 Dockerfile]
  build_service():   deploy/A3-service/service/     → .build/service/    [+ A3 Dockerfile]
  build_advanced():  deploy/A9-advanced/            → .build/advanced/
                     ├── service/      (as_dir, 含 aggregate/)  [+ A9 Dockerfile]
                     ├── MCPservice/   (as_dir)
                     └── copilot/      (as_dir)
  build_a5_endpoint(): deploy/A5-endpoint/python/    → .build/a5-endpoint/ [+ A5 Dockerfile]
```

**设计铁律**：
1. deploy/ 是中间产物 → **绝不修改 deploy/**
2. 只读 deploy/，只写 `.build/`
3. 容器定义取自分层手工维护的 `skeleton-container/{layer}/`

---

## 3. 核心约定速查

### 3.1 目录命名约定

| 约定 | 示例 | 说明 |
|------|------|------|
| **内层同名子目录** | `A2-copilot/copilot/`、`A9-advanced/service/` | 每个运行时层必须有自己的子目录层，不能平铺在根级 |
| **SKELETON_SUBDIRS 白名单** | `copilot`, `service`, `MCPservice`, `aggregate`... | 只有这些顶层目录被透传 |
| **\_EXCLUDED_FILES 过滤** | `.gitkeep`, `.gitignore`, `pytest.ini` | 构建时排除，不进 deploy |
| **产物命名** | `text-cli-A{layer}-v{ver}`、`text-cli-endpoint-{variant}-v{ver}` | 版本用下划线 |

### 3.2 路径硬依赖

```text
deploy/A2-copilot/          ← build.py --layer A2
deploy/A3-service/          ← build.py --layer A3
...
deploy/A9-advanced/         ← build.py --layer A9 (default)
deploy/A5-endpoint/python/  ← build-endpoint.py --variant python
docs/product_manuals/       ← 所有脚本的 docs_src
```

### 3.3 约定违背的典型症状

| 症状 | 根因 | 排查方向 |
|------|------|---------|
| `[ERR] deploy source not found` | `deploy/{layer}/` 不存在 | 检查 build-all.py 是否已运行 |
| `[ERR] docs template not found` | `docs_src` 路径指向不存在的位置 | 检查 `docs/product_manuals/` 是否存在 |
| `build-all.py --check` 报告 stale | deploy/ 中有不被任何源覆盖的旧文件 | 源重构后遗留，清理后重新构建 |
| Docker COPY 失败 | 构建上下文缺少预期的子目录 | 检查容器构建脚本的源路径是否正确 |
| 分发制品缺少子目录 | 使用了旧版抽取模式而非整目录拷贝 | 确认 build.py 使用 `--layer` + 整目录拷贝 |

---

## 4. 传播链路完整追踪

以 `text_cli_install.py` 为例——这是累积覆盖机制最重要的示范文件，说明为什么跨层同名文件必须只在一层持有。

```text
[1] 开发者编辑
    src/skeleton/service/A3-service/service/handlers/text_cli_install.py
    ← 唯一持有层。此文件包含完整的 install 逻辑（校验/部署/hot-reload/注册）。

[2] build-all.py 累积到 A4–A9
    deploy/A3-service/service/handlers/text_cli_install.py
    deploy/A4-paths/service/handlers/text_cli_install.py   ← A3 版本，累积继承
    deploy/A6-sql/service/handlers/text_cli_install.py     ← A3 版本，累积继承
    ...
    deploy/A9-advanced/service/handlers/text_cli_install.py ← A3 版本，累积继承

[3] 危险：如果 A4–A9 在源中持有各自的旧副本
    src/skeleton/service/A4-paths/service/handlers/text_cli_install.py  ← 旧版
    src/skeleton/service/A6-sql/service/handlers/text_cli_install.py    ← 旧版
    ...
    → build-all.py 后层覆盖前层 → A3 的修复被 A9 旧版覆盖 → 修复丢失
    → 正确做法：remove stale copies → A3 一份即可，累积链自然传递到所有层

[4a] 分发到 Win：build.py --layer A9
     deploy/A9-advanced/ 整目录拷贝 → skeleton-win/text-cli-A9-v*/service/handlers/text_cli_install.py

[4b] 分发到 Linux：build.py --layer A9
     同上，tar.gz 格式

[4c] 容器：build_advanced() 从 deploy/A9-advanced/service/ 拷贝
     skeleton-container/.build/advanced/service/handlers/text_cli_install.py
```

> **跨层修复纪律**：修任何累积层文件前，先 `find src/skeleton/service/ -path "*/目标文件名"` 确认分布。如果多个层持有同名文件，确认它们是否应合并（功能超集）或各自保留（层专有逻辑）。修复必须传播到所有持有该文件的层。

以 copilot 侧的 `text-cli-copilot.py` 为例——只在一层持有，追踪更简单：

```text
[1] 开发者编辑
    src/skeleton/copilot/A2-copilot/copilot/text-cli-copilot.py

[2] build-all.py 透传（A2 层）
    deploy/A2-copilot/copilot/text-cli-copilot.py

[3] build-all.py 累积到 A3–A9
    deploy/A3-service/copilot/text-cli-copilot.py
    ...
    deploy/A9-advanced/copilot/text-cli-copilot.py

[4a] 分发到 Win：build.py --layer A9
     deploy/A9-advanced/ 整目录拷贝 → skeleton-win/text-cli-A9-v*/copilot/text-cli-copilot.py
```

---

## 5. 新建层 checklist

当需要新增一个累积层时：

- [ ] `src/skeleton/{group}/{name}/` 下创建内层子目录
- [ ] 将运行时文件放入该内层子目录
- [ ] `build-all.py`：在 `LAYER_CHAIN` 追加新层
- [ ] `build-all.py`：如用了不在白名单的子目录，追加到 `SKELETON_SUBDIRS`
- [ ] `build-all.py`：如有新的开发文件类型，追加到 `_EXCLUDED_FILES`
- [ ] `build.py`：在 `LAYER_DEPLOY_MAP` 中追加新层映射
- [ ] `deploy/skeleton-container/`：如需容器，创建手工维护的 Dockerfile
- [ ] `deploy/INDEX_zh.md`：在层级导航表中追加新行
- [ ] 确认新层没有从低层继承的文件副本。
      运行 `find <new_layer> -type f | while read f; do rel="${f#<new_layer>/}"; [ -f A3-service/"$rel" ] && echo "STALE: $rel"; done`
      累积机制已保证低层文件传递到高层——重复持有 = 腐败副本。详见 §1.3 和 §4。
- [ ] 修复跨层 bug 时，先 `find src/skeleton/service/ -path "*/目标文件名"` 确认分布。
      所有持有副本的层同步修复，不要只改"最低层"就以为生效。
- [ ] 运行 `build-all.py --check` 全量验证

---

## 6. 协议校验脚本：check-protocol.py

`scripts/check-protocol.py` 是协议层静态校验工具——不与 CI 联动，按需手动运行。它与 `build-all.py` 分工正交：

| 维度 | `build-all.py` | `check-protocol.py` |
|------|:--:|:--:|
| 扫谁 | `src/skeleton/` ↔ `deploy/` 差异 | `src/skeleton/` + `schema.json` |
| 验证什么 | 文件是否同步 | 协议信封是否合规 |
| 粒度 | 文件级 | 字段级 |

### 6.1 规则

| # | 规则 | 扫谁 |
|:--:|------|------|
| 1 | `rst_err` ∈ 6 码闭集 ∪ {""} | A3 service 源码 |
| 2 | `rst_types` ∈ {text,picture,video,audio,file} | A3 service 源码 |
| 3 | 信封三字段 {rst_types, rst_data, rst_err} | A3 service 源码 |
| 4 | 入口格式 `AI:域;动作,参数` | A3 parser |
| 5 | 错误走 `rst_err` 主信号，不走 `rst_data.status:"error"` | A3 service 源码 |
| 6 | `pray_rst_types` 不泄漏到 `rst_data` | A3 service 源码 |
| 9 | `schema.json` 必填字段（id/name/type/runtime/category/locales/trust + directives[].domain/action/usage/description） | 所有标准包 |

### 6.2 用法

```bash
python scripts/check-protocol.py           # 全部规则
python scripts/check-protocol.py --rule 9  # 单条规则
python scripts/check-protocol.py --list    # 列出所有规则
python scripts/check-protocol.py --check   # CI 模式（exit 非零阻断）
```

### 6.3 设计边界

- 不扫 A0/A1（入站自由）
- 不扫 deploy/（扫真源 `src/skeleton/`，和 `build-all.py` 分工明确）
- 不加运行期白名单兜底——CI 即硬卡
- Rule 7（跨运行时同构）预留，暂不实现

---

*本文档是传播链的权威参考。如果行为和文档描述不一致，以脚本源码为准——并请更新此文档。*
