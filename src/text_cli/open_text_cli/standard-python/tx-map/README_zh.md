# 腾讯地图服务

腾讯地图 HTTP API 封装：地理编码、逆地理编码、路线规划、静态图、IP 定位。

## 安装

```
AI:text-cli;install,tx-map
```

## 依赖

- **运行时模块**：`text_cli_modules/key/`
- **凭据**：腾讯地图 API 密钥对（api_key + secret_key），通过 `AI:key;register,tx,<api_key>,<secret_key>,tencent_cloud` 注册

## 指令

| 指令 | 说明 |
|------|------|
| `腾讯地图;地理编码,<地址>` | 地址 → GCJ-02 坐标 |
| `腾讯地图;逆地理编码,<纬度>,<经度>` | GCJ-02 坐标 → 地址 |
| `腾讯地图;路线规划,<起点>,<终点>[,<格式>]` | 驾车路线（polyline/roads） |
| `腾讯地图;静态图,<纬度>,<经度>[,<缩放>,<尺寸>]` | 静态地图（base64 PNG） |
| `腾讯地图;IP定位,<IP>` | IP → 位置 |

## 示例

```
AI:腾讯地图;地理编码,威海市环翠区
AI:腾讯地图;逆地理编码,37.513,122.120
AI:腾讯地图;路线规划,威海站,威海公园
AI:腾讯地图;静态图,37.513,122.120,15,600
AI:腾讯地图;IP定位,119.190.214.126
```

## 架构

```
tx-map/
├── schema.json
├── handler.py
└── README_CN.md
```

handler 通过 `key_registry` 获取腾讯地图 api_key + secret_key，签名认证后调用腾讯地图 WebService API。
