# 百度云服务

百度云 API 封装：文字识别、百科查询、AI 搜索、视频笔记。

## 安装

```
AI:text-cli;install,bd-cloud
```

## 依赖

- **运行时模块**：`text_cli_modules/key/`
- **pip**：`requests`
- **凭据**：
  - `bd-ocr`：百度 OCR API 密钥对，`AI:key;register,bd-ocr,<api_key>,<secret_key>,api_key`
  - `bd-qianfan`：百度千帆 Bearer 令牌，`AI:key;register,bd-qianfan,<bearer>,bearer`

## 指令

| 指令 | 说明 |
|------|------|
| `百度云;文字识别,<图片URL或路径>` | 从图片提取文字 |
| `百度云;百科,<关键词>` | 查询百度百科词条 |
| `百度云;搜索,<查询>` | AI 网络搜索 |
| `百度云;视频笔记,<视频URL>` | 视频→AI 笔记（异步） |
| `百度云;视频笔记结果,<任务ID>` | 查询视频笔记任务结果 |

## 示例

```
AI:百度云;文字识别,https://example.com/receipt.png
AI:百度云;百科,威海
AI:百度云;搜索,今天天气
AI:百度云;视频笔记,https://example.com/video.mp4
```

## 架构

```
bd-cloud/
├── schema.json
├── handler.py
└── README_CN.md
```

handler 通过 `key_registry` 获取 bd-ocr（OCR OAuth）和 bd-qianfan（AI 服务 Bearer），调用百度云 API。
