# geo-grid · 地理网格工具

地理空间网格数学工具：H3 六边形索引、坐标计算、路线解析。

## 安装

```
AI:text-cli;install,geo-grid
```

## 依赖

- `h3`（pip）：`geo-grid;h3` 需要。其他指令仅用 Python 标准库。

## 指令

| 指令 | 说明 |
|------|------|
| `geo-grid;h3,<经度>,<纬度>[,<分辨率>]` | WGS84 → H3 格子 + 六边形边界 |
| `geo-grid;center,<lon1>,<lat1>,<lon2>,<lat2>` | 两点中心点 |
| `geo-grid;zoom,<lon1>,<lat1>,<lon2>,<lat2>` | 两点最佳地图缩放 |
| `geo-grid;zoom-from-distance,<米>` | 距离 → 缩放级别 |
| `geo-grid;h3-resolution,<米>` | 距离 → H3 分辨率 |
| `geo-grid;radius-bbox,<经度>,<纬度>,<米>` | 中心点 + 半径 → 边界框 |
| `geo-grid;offset,<经度>,<纬度>,<方位角>,<km>` | 原点 + 方位角 + 距离 → 目标点 |
| `geo-grid;route-parse,<JSON>,<来源>,<模式>` | 解析路线 JSON，提取有名道路 |

中文别名：`地理网格;六边形网格` `地理网格;中心点` 等。

## 示例

```
AI:地理网格;六边形网格,122.1,37.5,8
→ {"cell": "8830112ec3fffff", "boundary": [[...]]}

AI:地理网格;偏移,122.1,37.5,90,10
→ {"lon": 122.21, "lat": 37.5}
```

## 架构

```
Python 包（含 pip 依赖）
  ├── handler.py    — @directive 注册 + 纯数学 + h3
  └── schema.json   — 8 条指令
```
