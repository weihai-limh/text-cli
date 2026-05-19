# geo-grid

Geospatial grid mathematics — H3 hexagonal indexing, coordinate calculations, and route parsing.

## Install

```
AI:text-cli;install,geo-grid
```

## Dependencies

- `h3` (pip): required for `geo-grid;h3`. Other directives use Python stdlib only.

## Directives

| Directive | Description |
|-----------|-------------|
| `geo-grid;h3,<lon>,<lat>[,<res>]` | WGS84 → H3 cell + hex boundary |
| `geo-grid;center,<lon1>,<lat1>,<lon2>,<lat2>` | Midpoint between two coordinates |
| `geo-grid;zoom,<lon1>,<lat1>,<lon2>,<lat2>` | Optimal map zoom for two points |
| `geo-grid;zoom-from-distance,<meters>` | Distance → zoom level |
| `geo-grid;h3-resolution,<meters>` | Distance → H3 resolution |
| `geo-grid;radius-bbox,<lon>,<lat>,<meters>` | Center + radius → bounding box |
| `geo-grid;offset,<lon>,<lat>,<bearing>,<km>` | Origin + bearing + distance → target |
| `geo-grid;route-parse,<json>,<source>,<mode>` | Parse route JSON, extract named roads |

## Example

```
AI:geo-grid;h3,122.1,37.5,8
→ {"cell": "8830112ec3fffff", "boundary": [[...]]}

AI:geo-grid;center,122.0,37.0,122.2,37.2
→ {"lon": 122.1, "lat": 37.1}

AI:geo-grid;offset,122.1,37.5,90,10
→ {"lon": 122.21, "lat": 37.5}
```

## Architecture

```
Python package with pip dependency
  ├── handler.py    — @directive registration + pure-math + h3
  └── schema.json   — 8 directives
```
