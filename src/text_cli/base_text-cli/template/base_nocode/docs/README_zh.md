# converter_template.py 使用说明书

## 这是什么

`converter_template.py` 是一个单文件模板——将结构化 Markdown 经验文档转化为 text-cli 指令服务。

零依赖，纯 Python 标准库。人和 AI 通过同一个 HTTP 端点消费。

## 文件夹结构

```
base_nocode/
├── converter_template.py          ← 通用模板（你的起点）
├── template.md                    ← Markdown 规格模板（你的 Markdown 按这个写）
├── docs/
│   └── README.md                  ← 本文件
├── zh/                            ← 中文实例（参考）
│   ├── markdown_converter_zh.py   ← 模板填好后的样子
│   ├── 盆栽急救手册_zh.md         ← 中文经验文档
│   └── README.md
└── en/                            ← 英文实例（参考）
    ├── markdown_converter_en.py   ← 模板填好后的样子
    ├── Bonsai-First-Aid-Manual_en.md ← 英文经验文档
    └── README.md
```

## 三步上手

### 第一步：写经验文档

按 `template.md` 的格式写一份 Markdown（支持中英双语节标题）：

```markdown
## 指令定义
- 领域: 汽车维修
- 动作: 诊断
- 触发词: 发动机, 刹车, 机油, 异响
- 参数: 部位, 症状

## 经验内容
### 发动机
#### 无法启动
- 原因: 电瓶亏电或起动机故障。
- 处理: 搭电或更换电瓶。检查起动机继电器。
- 预防: 每 3-5 年更换电瓶。
```

关键规则：
- `## 指令定义`（或 `## Directive`）块定义领域和动作
- `## 经验内容`（或 `## Knowledge`）块是知识内容
- `###` 是一级分类，`####` 是二级分类

### 第二步：拷贝模板

```bash
cp converter_template.py my-car-repair.py
```

打开 `my-car-repair.py`，改顶部的变量：

```python
Domain = "汽车维修"
Action = "诊断"
Host = "0.0.0.0"
Port = 8000
AuthEnabled = False
ServiceToken = ""
```

`Host` 和 `Port` 也可通过命令行参数覆盖：

```bash
python my-car-repair.py 汽车故障手册.md --port 9000 --host 127.0.0.1
```

### 第三步：启动

```bash
python my-car-repair.py 汽车故障手册.md
```

服务启动后即可调用：

```bash
curl -X POST http://localhost:8000/text-cli/cli \
  -H "Content-Type: application/json" \
  -d '{"prompt": "AI:汽车维修;诊断,发动机,无法启动"}'
```

## 自定义 handler

如果默认的 `category → sub` 两级检索不匹配你的参数结构，修改 `[Custom 3/3]` 区的 `handler()` 函数。

默认逻辑：
```
无参数     → 列出所有分类
一个参数   → 列出该分类的所有子类
两个参数   → 精确匹配分类+子类，找不到则降级到只匹配分类
```

改完之后重启服务即可生效。

## 加 token 鉴权

```python
AuthEnabled = True
ServiceToken = "my-secret"
```

开启后调用方须在请求头带 `Service-token: my-secret`。token 不匹配返回 `SERVICE_DENIED`。

## 参考实例

| 实例 | 领域 | 动作 | 语言 |
|------|------|------|:--:|
| `zh/` | 家庭园艺 | 盆栽急救 | 中文 |
| `en/` | home-gardening | plant-first-aid | 英文 |

每个实例都是 `converter_template.py` 填好变量后的完整可运行版本。参考它们了解 handler 改完后的完整形态。


