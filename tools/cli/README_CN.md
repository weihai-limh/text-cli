# cli — 将 Agent 既有资源转化为 text-cli 指令

## 核心理念

Agent 往往已经有大量可用能力——本地函数、API 调用、知识库、工具链。`cli/` 提供将**既有资源**包装为 text-cli 标准指令的方法论和模板。

## 转化流程

```
Agent 既有能力
    │
    ├── 本地函数    → @cli.register(领域, 动作) → HTTP 端点
    ├── API 调用     → 封装为指令处理器           → HTTP 端点
    ├── 知识库      → 定义为查询领域             → HTTP 端点
    └── 工具链      → 指令化包装                → HTTP 端点

                    ↓
          发布 Schema → Service Token → 其他 Agent 可调用
```

## 三步转化法

### 第一步：能力盘点

列出你已有的所有能力，问自己三个问题：

| 问题 | 示例 |
|------|------|
| 这个能力**做什么**？ | 查询天气、翻译文本、计算哈希 |
| 谁需要它？ | 自己的用户、其他 Agent、人类 |
| 参数是什么？ | 城市+日期、文本+目标语言、字符串+算法 |

### 第二步：领域与动作设计

```
领域 = 能力的"类别"（名词）
动作 = 能力的"做什么"（动词）

规则:
  - 领域和动作使用中文
  - 领域一般 ≤ 4 个字
  - 动作一般 ≤ 2 个字
  - 一个领域下可以有多个动作
```

**设计示例**：

| 既有能力 | 领域 | 动作 | 指令 |
|----------|------|------|------|
| 天气查询 | 天气 | 查询 | `AI:天气;查询,明天,威海` |
| 翻译服务 | 翻译 | 中译英 | `AI:翻译;中译英,你好世界` |
| 计算器 | 数学 | 计算 | `AI:数学;计算,2+3*4` |
| 文件读取 | 文件 | 读取 | `AI:文件;读取,/path/to/file` |
| 网页抓取 | 网页 | 抓取 | `AI:网页;抓取,https://example.com` |

### 第三步：指令处理器实现

使用 `cli.py` 中的 `@cli.register` 装饰器将既有函数映射为指令处理器。

```python
from cli import register

@register("天气", "查询")
def weather_query(params):
    city = params[0] if params else "北京"
    date = params[1] if len(params) > 1 else "今天"
    # 调用你已有的天气 API
    return my_existing_weather_api(city, date)
```

## 设计原则

1. **指令即文档。** 指令格式本身应能描述能力（`AI:天气;查询` 自解释）
2. **参数极简。** 位置参数，逗号分隔，不引入 JSON 嵌套
3. **文本返回。** `rst_types: text`，人机皆可读
4. **幂等优先。** 查询类指令多次调用返回相同结果

## 文件结构（按实现方式组织）

```
cli/
├── README.md
├── python/                   ← Python 实现
│   ├── cli.py               ← 核心：@register 装饰器 + 指令服务器启动
│   └── handlers/
│       ├── __init__.py
│       └── sample.py        ← 三类转化示例（API / 工具 / 知识库）
└── (NoCode 实现见 CN/cli/nocode/)
```

## 完整示例：Markdown → 指令

`CN/cli/nocode/markdown_converter.py` 是 **三步转化法** 的完整实现，参考 `docs/CN/Markdown2Text-cli_CN.md`：

```bash
# 启动
cd CN/cli/nocode
python markdown_converter.py 盆栽急救手册.md

# 调用
curl -X POST http://localhost:8000/cli/text_cli \
  -H "Content-Type: application/json" \
  -d '{"prompt": "AI:家庭园艺;盆栽急救,绿萝,叶片发黄"}'

# 返回
🌱 绿萝 · 叶片发黄
原因：浇水过多或光照不足。
急救：立即停止浇水，移到散射光处，剪掉黄叶...
```

**它做了什么**：
1. 解析结构化 Markdown → 提取「指令定义」元数据 + 「经验内容」条目
2. `@register("家庭园艺", "盆栽急救")` 自动注册指令处理器
3. 用户调用 `AI:家庭园艺;盆栽急救,绿萝,叶片发黄` → 精确匹配或模糊检索 → 格式化返回

这正是 Markdown2Text-cli 理念的 Agent 侧实现：**非开发者写 MD，Agent 代运营指令。**

## 与 server/python 的关系

| | `agent/cli/` | `server/python/` |
|---|---|---|
| 定位 | 轻量转化层 | 完整指令服务 |
| 依赖 | 无框架 | FastAPI |
| 适用 | 快速将既有能力指令化 | 独立部署的指令服务端点 |
| 输出 | Python 模块 + Schema | HTTP 服务 + Docker |
