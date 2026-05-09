# AI辅助指令示例

> Domain: `AI辅助` | 更新: 2026-05-09 | 实现: `text_cli_modules/ai/inference.py`

## 指令清单

| 指令 | 级别 | 参数 | 说明 |
|------|------|------|------|
| `AI辅助;推理` | read | 提示词, 模式(可选) | 纯文本推理，多模型回退链 |
| `AI辅助;视觉` | read | 提示词, 图片URL, 模式(可选) | 视觉推理（文本+图片） |

## 模式参数

| 模式 | 说明 |
|------|------|
| `auto` | 默认。时段感知：0-6时付费模型，6-24时免费模型 |
| `fast` | 强制免费链 zhipu glm-4-flash → xunfei lite |
| `quality` | 强制付费链 xxx (GLM-5/Kimi-K2.5/MiniMax-M2.5) |
| `<模型名>` | 直接指定，如 `glm-4-flash-250414` |

## 回退链机制

```
提供者A 模型1 → 失败?
  └→ 模型2    → 失败?
    └→ 提供者B 模型1 → 失败?
      └→ 模型2    → ...
        └→ 第一个成功的结果被返回
```

- **fast 链**: zhipu → xunfei
- **quality 链**: xxx (多模型轮询)
- 每个模型独立超时 60s，不阻塞

---

## 指令:AI辅助;推理

**用途**：将提示词发送给 LLM，返回推理结果。自动选择最优模型（便宜优先）。

**调用示例**：

纯文本（协议原生）：
```
指令:AI辅助;推理,用一句话解释什么是 CAP 定理,auto
```

HTTP（通过 service 代理）：
```bash
curl -X POST http://localhost:8000/cli/text_cli \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "command": "AI辅助;推理",
    "parameters": ["用一句话解释什么是 CAP 定理", "auto"]
  }'
```

**响应**（纯文本）：
```
CAP定理指出分布式系统无法同时满足一致性(Consistency)、可用性(Availability)和分区容错性(Partition tolerance)，最多只能同时满足其中两个。
```

**显式降低消费**：将 `auto` 替换为 `fast`。系统将只使用低消费端。

---

## 指令:AI辅助;视觉

**用途**：分析图片内容。支持 http/https URL 或 base64 data URI。

**调用示例**：

纯文本（协议原生）：
```
指令:AI辅助;视觉,描述这张图片的内容,https://picsum.photos/400/300,auto
```

HTTP（通过 service 代理）：
```bash
curl -X POST http://localhost:8000/cli/text_cli \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "command": "AI辅助;视觉",
    "parameters": ["描述这张图片的内容", "https://picsum.photos/400/300", "auto"]
  }'
```

**响应**（纯文本）：
```
这是一张风景照片，展示了壮丽的山脉，前景是一片绿色的草地，天空中有少许云层。
```

---

## 实现说明

- **核心模块**：`text_cli_modules/ai/inference.py`
  - `text_inference(prompt, api_keys, mode)` — 纯文本推理
  - `vision_inference(prompt, image_url, api_keys, mode)` — 视觉推理
  - `get_period(tz_offset=8)` — 时段检测（1=夜间 2=白天 3=晚间）
- **依赖**：仅 `urllib` stdlib，零外部依赖
- **密钥**：从 `key_registry` 读取 `zhipu`/`xunfei`/`modelscope` 的 api_key
- **提供者**：zhipu (GLM-4 系列) / xunfei (Spark Lite) / XXX (多模型)
