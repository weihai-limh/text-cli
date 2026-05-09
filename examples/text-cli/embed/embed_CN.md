# 语义嵌入指令示例

> Domain: `语义` | 更新: 2026-05-09 | 实现: `text_cli_modules/embed/embedding_3.py`

## 指令清单

| 指令 | 级别 | 参数 | 说明 |
|------|------|------|------|
| `语义;编码` | read | 文本, 维度模式(可选) | 将文本编码为语义向量 |
| `语义;相似` | read | 文本A, 文本B, 维度模式(可选) | 计算两段文本的语义相似度 |
| `语义;匹配` | read | 查询, 候选1, 候选2, ..., 维度模式(可选) | 从候选中找出语义最匹配的一项 |

## 维度模式

| 模式 | 维度 | 适用场景 |
|------|------|---------|
| `A` | 256 | 快速比对，精度要求低 |
| `B` | 512 | 默认。通用场景 |
| `C` | 1024 | 高精度检索 |
| `D` | 2048 | 极致精度，论文级 |

## 引擎

- **主力**：`bigmodel/embedding-3`（在线 API，免冷启动）
- **守卫**：`BAAI/bge-m3`（CF Worker 本地，cosine < 0.7 时激活）
- 策略详见 `docs/CN/up_embedding_0509.md`

---

## 指令:语义;编码

**用途**：将文本转为浮点向量，供后续相似度计算或检索使用。

**调用示例**：

纯文本（协议原生）：
```
指令:语义;编码,今天天气真好,B
```

HTTP（通过 service 代理）：
```bash
curl -X POST http://localhost:8000/cli/text_cli \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "command": "语义;编码",
    "parameters": ["今天天气真好", "B"]
  }'
```

**响应**：
```
已编码 (512维)
预览: [0.014523, -0.003421, 0.021987, ...]...
```

---

## 指令:语义;相似

**用途**：计算两段文本的语义相似度，返回分数+文字判定。

**调用示例**：

纯文本（协议原生）：
```
指令:语义;相似,今天天气真好,天气很棒,B
```

HTTP（通过 service 代理）：
```bash
curl -X POST http://localhost:8000/cli/text_cli \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "command": "语义;相似",
    "parameters": ["今天天气真好", "天气很棒", "B"]
  }'
```

**响应**：
```
相似度: 92.3%
判定: 高度相似 — 几乎在说同一件事
```

**判定阈值**：
| 分数 | 判定 |
|------|------|
| > 85% | 高度相似 |
| 70-85% | 较强相似 |
| 50-70% | 中度相似 |
| 30-50% | 弱相关 |
| < 30% | 不相关 |

---

## 指令:语义;匹配

**用途**：从多个候选中找出与查询最匹配的一项。

**调用示例**：

纯文本（协议原生）：
```
指令:语义;匹配,海边的风很大,沙滩阳光浴,台风预警,内陆平原,B
```

HTTP（通过 service 代理）：
```bash
curl -X POST http://localhost:8000/cli/text_cli \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "command": "语义;匹配",
    "parameters": ["海边的风很大", "沙滩阳光浴", "台风预警", "内陆平原", "B"]
  }'
```

**响应**：
```
最佳匹配 (85.6%): 台风预警

  1. [85.6%] 台风预警
  2. [62.1%] 沙滩阳光浴
  3. [15.3%] 内陆平原
```

---

## 实现说明

- **核心模块**：`text_cli_modules/embed/embedding_3.py`
  - `encode(text, api_key, dims)` — 单文本编码
  - `encode_batch(texts, api_key, dims)` — 批量编码
  - `similarity(a, b, api_key, dims)` — 余弦相似度
  - `match(query, candidates, api_key, dims)` — 最佳匹配
- **依赖**：仅 `urllib` stdlib，零外部依赖
- **密钥**：从 `key_registry` 读取 `bigmodel-embedding-3` 的 api_key
- **API**：`https://open.bigmodel.cn/api/paas/v4/embeddings`
