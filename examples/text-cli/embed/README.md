# Semantic Embedding

**Directives:** `语义;编码`, `语义;相似`, `语义;匹配`
**Dependencies:** `text_cli_modules/embed/`
**Configuration:** Model alias in `model_aliases.json` (embedding section)

Encode text into vector embeddings, compute pairwise similarity, and find best matches.

## Install

```bash
cp examples/text-cli/embed/handler.py server/python/handlers/embed.py
```

## Usage

```
AI:语义;编码,The winter sea wind in Weihai is strong
AI:语义;相似,Weihai winters are cold,The winter sea wind in Weihai is strong
AI:语义;匹配,The weather is great today,Weihai winters are cold;It rained today;Spring has arrived,3
```

---

# 语义嵌入

**指令:** `语义;编码`, `语义;相似`, `语义;匹配`
**依赖:** `text_cli_modules/embed/`
**配置:** `model_aliases.json` 中的 embedding 段落

将文本编码为向量嵌入、计算相似度、寻找最佳匹配。

## 安装

```bash
cp examples/text-cli/embed/handler.py server/python/handlers/embed.py
```

## 使用

```
指令:语义;编码,威海的冬天海风很大
指令:语义;相似,威海冬天很冷,威海的冬天海风很大
指令:语义;匹配,今天天气真好,威海冬天很冷;今天下雨了;现在是春天,3
```
