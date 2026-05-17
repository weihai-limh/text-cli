# path 和 aggregate — 编排与路由

两套声明式系统。同一件事的两个维度——**先后**和**谁做**。

---

## 一、path：管先后

path 是编排层。它把多条指令串成链，声明"先做什么，再做什么，上一步的输出怎么传给下一步"。

```json
{
  "id": "route-map",
  "steps": [
    {
      "id": "start",
      "directive": "map;geocode,${input}",
      "output_as": "start"
    },
    {
      "id": "end",
      "directive": "map;geocode,${input}",
      "output_as": "end"
    },
    {
      "id": "route",
      "directive": "map;route,{start.lat},{start.lon},{end.lat},{end.lon}",
      "output_as": "route"
    }
  ]
}
```

### 核心机制

| 语法 | 含义 | 示例 |
|------|------|------|
| `${input}` | 用户输入占位符 | `weather;query,${input}` |
| `{step.field}` | 上一步输出的字段 | `{start.lat}` |
| `output_as` | 捕获步骤输出为变量 | `"output_as": "start"` |

### 管道闭包原则

**路径只做编排和插值。文件 IO、API 调用、推理——全部通过指令完成。**

```
路径: 编排指令序列（step1 → step2 → step3）
指令: 执行具体操作（tc-markdown;read, ai;infer, map;geocode）
```

路径引擎不读文件——它调 `tc-markdown;read`。不推理——它调 `ai;infer`。不调 API——它调 `map;geocode`。这个边界是设计红线。

---

## 二、aggregate：管谁做

aggregate 是路由层。它声明一个入口对应多个提供方，按降级链依次尝试。

```json
{
  "id": "map",
  "type": "aggregate",
  "domain": "map",
  "default": ["x1-map", "x2-map", "x3-map"],
  "providers": {
    "x1-map": {"geocode": "x1-map;geocode"},
    "x2-map": {"geocode": "x2-map;geocode"},
    "x3-map": {"geocode": "x3-map;geocode"}
  }
}
```

### 降级链

```
map;geocode,威海
  → x1-map;geocode   → 配额耗尽 → 跳过
  → x2-map;geocode   → MCP 不可用 → 跳过
  → x3-map;geocode   → ok → 返回
```

降级触发条件：返回 `status: "stop"`（配额耗尽）、返回错误、指令未注册。

### 不区分来源

提供方可以是 native handler、MCP bridge、Skill Bridge——聚合引擎不关心。它只按降级链依次调 `dispatch()`。

### 多源统一

```
一个 map;geocode 入口
背后三条可能路径：
  - native handler（指令包开发）
  - MCP bridge（MCP 映射接入）
  - Skill bridge（skill 映射接入）
```

---

## 三、path + aggregate 的协作

```json
{
  "steps": [
    {
      "id": "geo",
      "directive": "map;geocode,${input}",   ← aggregate: 降级链选提供方
      "output_as": "geo"
    },
    {
      "id": "weather",
      "directive": "weather;query,{geo.lat},{geo.lon}",  ← 直接用聚合结果
      "output_as": "weather"
    }
  ]
}
```

path 不关心 `map;geocode` 背后是谁——它在 aggregate 里已被收敛为单一入口。path 只说"先 geocode 再查天气"，aggregate 说"geocode 有三家可以试"。

---

## 四、对比

| | path | aggregate |
|------|------|------|
| 解决的问题 | 先做什么，再做什么 | 找谁来做 |
| 配置位置 | `paths/` 目录 | `aggregate/` 目录（A8-discovery 下） |
| 加载时机 | `text-cli;path` 注册 | 启动时自动扫描 |
| 消费方 | template;use | dispatch 引擎 |
| 典型场景 | 天气→穿衣建议链 | 三家地图自动降级 |
