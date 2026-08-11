# zhihu-cloud — 知乎开放平台搜索

通过知乎开放平台 API 搜索站内内容和全网索引。

## 安装

```
AI:text-cli;install,zhihu-cloud
```

## 依赖

- **pip**: `requests`
- **运行时模块**: `text_cli_modules/key/`（A6 骨架已预部署）
- **凭据**: key_registry 中的 `zhihu` access_secret

## 指令

| 领域 | 动作 | 签名 | 说明 |
|------|------|------|------|
| zhihu-cloud | search | `zhihu-cloud;search,<关键词>[,<条数>]` | 知乎站内搜索（文章 + 回答），最多 10 条 |
| zhihu-cloud | global-search | `zhihu-cloud;global-search,<关键词>[,<条数>[,<JSON>]]` | 全网搜索 zhihu-share 索引库，最多 20 条 |

### search — 站内搜索

搜索知乎站内的文章和回答。每条结果返回 6 个核心字段：`title`、`url`、`snippet`（≤300 字摘要）、`content_type`（article/answer）、`authority_level`（1-4 权威等级）、`voteup_count`（赞同数）。

```json
// 返回示例
{
  "status": "ok",
  "source": "zhihu",
  "query": "AI评测",
  "sources": [
    {
      "title": "AI评测方法综述",
      "url": "https://zhuanlan.zhihu.com/p/123456789",
      "snippet": "本文介绍了主流AI评测框架...",
      "content_type": "article",
      "authority_level": "2",
      "voteup_count": 128
    }
  ],
  "count": 10,
  "count_requested": 10
}
```

### global-search — 全网搜索

搜索知乎索引库中的全网内容，支持高级筛选表达式。

`<JSON>` 可选参数：

| 字段 | 类型 | 说明 |
|------|------|------|
| `filter` | string | 高级筛选表达式：`host=="example.com"`、`publish_time>=1740000000`、`AND`/`OR` |
| `search_db` | string | 索引库选择：`all`（默认）、`realtime`、`static` |

## 示例

```
AI:zhihu-cloud;search,RAG评测,5
AI:zhihu-cloud;global-search,开源大模型,10
AI:zhihu-cloud;global-search,大模型,5,{"filter":"publish_time>=1719705600","search_db":"realtime"}
```

## 文件结构

```
zhihu-cloud/
├── DESIGN.md
├── schema.json
├── handler.py
├── README.md           ← 纯英文（本文件）
├── README_CN.md        ← 纯中文
└── demo.py             ← API 参考文档（不随包部署）
```

## 设计说明

- **返回值归约**：API 原始 Item 含 15+ 字段，handler 层归约为 AI 消费需要的 6 个核心字段（对标 bd-cloud;search 的返回风格）
- **URL 清洗**：自动去除 `utm_*` 溯源参数
- **摘要截断**：300 字符，尽量句边界截断
- **凭据**：从 A3 key_registry 里的 `zhihu` 条目读取
