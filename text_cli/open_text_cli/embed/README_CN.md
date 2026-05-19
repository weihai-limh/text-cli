# embed · 语义嵌入

文本嵌入、相似度比较与语义匹配，基于可配置的嵌入供应商。

## 安装

```
AI:text-cli;install,embed
```

## 依赖

**运行时模块**（需部署到服务）：
- `text_cli_modules/embed/` — 嵌入引擎

**凭据**：
- 嵌入供应商 API 密钥：`AI:key;注册,embedding_api_key,<key值>,api_key`

## 指令

| 指令 | 说明 |
|------|------|
| `semantic;encode,<文本>[,<模式>]` | 文本转向量。模式：A=256, B=512（默认）, C=1024, D=2048 |
| `semantic;similarity,<文本A>,<文本B>[,<模式>]` | 计算成对相似度（0-1） |
| `semantic;match,<查询>,<候选1>,<候选2>,...[,<模式>]` | 在候选中找最佳匹配 |

## 示例

```
AI:语义;编码,威海的冬天海风很大
→ [0.0123, -0.0456, 0.0789, ...]  (512 维)

AI:语义;相似,威海冬天很冷,威海的冬天海风很大
→ {"similarity": 0.87}

AI:语义;匹配,今天天气真好,威海冬天很冷;今天下雨了;现在是春天,3
→ {"best_match": "现在是春天", "similarity": 0.72, "index": 2}
```

## 架构

```
A3 Service 扩展
  ├── handler.py           — @directive 注册 + 业务逻辑
  ├── schema.json          — 指令声明
  └── text_cli_modules/embed/ — 嵌入引擎（运行时依赖）
```
