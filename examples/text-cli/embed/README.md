# Semantic Embedding

**Directives:** `semantic;encode` (alias: `语义;编码`), `semantic;similar` (alias: `语义;相似`), `semantic;match` (alias: `语义;匹配`)
**Dependencies:** `text_cli_modules/embed/`
**Configuration:** Model alias in `model_aliases.json` (embedding section)

Encode text into vector embeddings, compute pairwise similarity, and find best matches.

## Install

```bash
cp examples/text-cli/embed/handler.py server/python/handlers/embed.py
```

## Usage

```
AI:semantic;encode,The winter sea wind in Weihai is strong
AI:semantic;similar,Weihai winters are cold,The winter sea wind in Weihai is strong
AI:semantic;match,The weather is great today,Weihai winters are cold;It rained today;Spring has arrived,3
```

---

# 语义嵌入

**指令:** `semantic;encode` (别名: `语义;编码`), `semantic;similar` (别名: `语义;相似`), `semantic;match` (别名: `语义;匹配`)
**依赖:** `text_cli_modules/embed/`
**配置:** `model_aliases.json` 中的 embedding 段落

将文本编码为向量嵌入、计算相似度、寻找最佳匹配。

## 安装

```bash
cp examples/text-cli/embed/handler.py server/python/handlers/embed.py
```

## 使用

```
AI:semantic;encode,威海的冬天海风很大
指令:语义;编码,威海的冬天海风很大
AI:semantic;similar,威海冬天很冷,威海的冬天海风很大
AI:semantic;match,今天天气真好,威海冬天很冷;今天下雨了;现在是春天,3
```
