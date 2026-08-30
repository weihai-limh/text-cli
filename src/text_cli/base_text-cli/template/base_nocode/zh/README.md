# 盆栽急救 · 中文

这个文件夹是一个自包含的 text-cli 指令服务。拷走就能跑。

## 文件

| 文件 | 说明 |
|------|------|
| `markdown_converter_zh.py` | 指令服务（改 `Domain`/`Action` 两变量即可换指令，不改则自动从 Markdown 提取） |
| `盆栽急救手册_zh.md` | 经验内容——改这个就等于更新知识库 |
| `README.md` | 本文件 |

## 启动

```bash
python markdown_converter_zh.py 盆栽急救手册_zh.md
```

输出 `服务: http://localhost:8000/text-cli/cli` 即启动完成。

## 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/text-cli/cli` | POST | 执行指令（`AI:域;动作,参数`） |
| `/text-cli/cli` | POST | 指令发现（`AI:text-cli;query,json`） |
| `/text-cli/schema` | GET | 指令 schema（含可信度信息） |
| `/text-cli/health` | GET | 健康检查 |

## 查询

```bash
# 查询具体症状
curl -X POST http://localhost:8000/text-cli/cli \
  -H "Content-Type: application/json" \
  -d '{"prompt": "AI:家庭园艺;盆栽急救,绿萝,叶片发黄"}'

# 列出绿萝的所有问题
curl -X POST http://localhost:8000/text-cli/cli \
  -H "Content-Type: application/json" \
  -d '{"prompt": "AI:家庭园艺;盆栽急救,绿萝"}'

# 列出所有植物
curl -X POST http://localhost:8000/text-cli/cli \
  -H "Content-Type: application/json" \
  -d '{"prompt": "AI:家庭园艺;盆栽急救"}'

# 查看指令 schema（含可信度信息）
curl http://localhost:8000/text-cli/schema

# 指令发现（与 schema 端点返回相同内容）
curl -X POST http://localhost:8000/text-cli/cli \
  -H "Content-Type: application/json" \
  -d '{"prompt": "AI:text-cli;query,json"}'

# 健康检查
curl http://localhost:8000/text-cli/health
```

### 响应格式

精确匹配时 `rst_data` 返回：

```json
{
  "status": "ok",
  "category": "绿萝",
  "sub": "叶片发黄",
  "content": "- 原因: 浇水过多或光照不足...\n- 处理: ...\n- 鉴别: ...\n- 教训: ..."
}
```

降级匹配时（症状未精确命中）：

```json
{
  "status": "ok",
  "category": "绿萝",
  "sub": null,
  "items": [
    {"sub": "叶片发黄", "content": "..."},
    {"sub": "烂根", "content": "..."}
  ]
}
```

## 加 token 鉴权

同一位置的两个变量控制请求鉴权：

```python
AuthEnabled = True          # 开启：请求必须带 token
ServiceToken = "my-secret"  # token 值
```

开启后，调用方须在请求头带 `Authorization: Bearer <token>`。

```bash
curl -X POST http://localhost:8000/text-cli/cli \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer my-secret" \
  -d '{"prompt": "AI:家庭园艺;盆栽急救,绿萝,叶片发黄"}'
```

token 不匹配返回 `SERVICE_DENIED`。`AuthEnabled=False`（默认）则全放行。

## 更新经验内容

编辑 `盆栽急救手册_zh.md`，格式如下，然后重启服务：

```markdown
## 指令定义
- 领域: 你的领域
- 动作: 你的动作
- 触发词: 关键词, 另一个关键词
- 参数: 参数一, 参数二
- 来源: 你的来源          # 可选 — 知识出处
- 核实: 核实人,日期        # 可选 — 核实记录
- 过期: 2026-12-31         # 可选 — 过期日期
- 状态: stable             # 可选 — draft | stable | deprecated

## 经验内容
### 分类名
#### 子分类名
- 原因: ...
- 处理: ...
- 预防: ...
- 鉴别: ...               # 可选 — 如何与相似问题区分
- 教训: ...               # 可选 — 血泪教训
```

- 每条 `###` 是一个分类，`####` 是一个子分类。
- `来源`/`核实`/`过期`/`状态` 全部可选——有则显示在 schema 中，无则不影响。
- `鉴别`/`教训` 为约定写法——解析器不做特殊处理，写了就返回，不写就没有。

## 改端口

```bash
python markdown_converter_zh.py 盆栽急救手册_zh.md --port 9000
```

或改文件头部的变量：

```python
Host = "127.0.0.1"
Port = 9000
```

命令行参数优先于文件变量。

## 改指令

打开 `markdown_converter_zh.py`，改文件头部的变量：

```python
Domain = "你的领域"    # 留空 "your-domain" 则自动从 Markdown 提取
Action = "你的动作"    # 留空 "your-action" 则自动从 Markdown 提取
```

不改则自动从 Markdown 的 `## 指令定义` 中提取。显式修改则覆盖 Markdown 中的值。

然后改 `handler()` 函数里的检索逻辑以匹配你的参数结构。重启服务生效。
