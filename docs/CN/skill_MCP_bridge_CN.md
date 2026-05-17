# skill 和 MCP 桥 — 映射机制及如何映射

两者都是"把外部工具变成 text-cli 指令"。区别在来源：skill 来自技能市场，MCP 来自 MCP Server。

---

## 一、skill bridge — 技能市场桥接

### 流程

```
ClawHub 下载 skill → copilot/skills/<name>/
  → skill_bridge_routes.json 声明路由
  → skill_bridge.py 执行 skill 脚本
  → 适配器归一化输出
  → 返回 text-cli 指令结果
```

### 路由配置

```json
{
  "skill-bdmap;geocode": {
    "skill": "baidu-ai-map",
    "command": "python3 {skill_dir}/scripts/baidumap.py geocode '{address}'",
    "adapter": "baidumap",
    "output_adapter": "baidu-map/geocode",
    "timeout_ms": 15000
  }
}
```

| 字段 | 说明 |
|------|------|
| `skill` | ClawHub skill 目录名 |
| `command` | 执行命令模板，`{skill_dir}` 自动替换为 skills/<name> |
| `adapter` | 通用适配器——status 归一化（如 baidumap: status 0→ok） |
| `output_adapter` | Provider 专用适配器——字段映射到规范格式 |
| `timeout_ms` | 超时时间 |

### 适配器分层

```
skill 脚本 stdout → 通用适配器（status 归一化）→ output_adapter（字段映射）→ 规范格式
```

通用适配器不感知具体 provider——所有 skill 共享同一套 status 归一化。Provider 适配器只做字段映射——每个 provider 一个文件。

```
copilot/adapters/
  baidu-map/
    geocode.py    ← Baidu API 字段 → text-cli 规范格式
```

### 映射怎么写

1. 从 ClawHub 拉取 skill：`git clone <skill-url> skills/<name>`
2. 在 `skill_bridge_routes.json` 加路由条目
3. 如果 skill 输出格式不标准——写通用适配器（status 归一化）
4. 如果字段需要映射到规范格式——写 output_adapter（`adapters/<provider>/`）

---

## 二、MCP bridge — MCP 生态桥接

### 流程

```
MCP Server → mcp_handler.py → text-cli 指令
             mcp2textcli 编译 → schema.json
```

### 配置

`mcp_exposure.json` 声明 MCP server 连接：

```json
{
  "tencent-maps": {
    "transport": "sse",
    "url": "http://localhost:3001/sse"
  }
}
```

### 自动编译

`mcp2textcli` 扫描 MCP server 的 tools/list → 自动生成 schema.json → 指令注册。passthrough 指令（纯文本参数）100% 自动，无需手写。

| | GitHub | AntV | 腾讯地图 | CloudBase |
|---|---:|---:|---:|---:|
| Tools | 26 | 26 | 15 | 36 |
| passthrough | 92% | 8% | 100% | 89% |
| 需手写 adapter | 2 | 0 | 0 | 4 |

> 四个 Server 共 103 个 tools，总计需手写 6 个 adapter。接入效率：94% 零手写。

---

## 三、skill 和 MCP 在聚合层汇合

```json
{
  "id": "map",
  "default": ["x1-map", "tencent-maps", "skill-bdmap"],
  "providers": {
    "x1-map":        {"geocode": "x1-map;geocode"},       ← native handler
    "tencent-maps":  {"geocode": "tencent-maps;geocode"},  ← MCP bridge
    "skill-bdmap":   {"geocode": "skill-bdmap;geocode"}    ← skill bridge
  }
}
```

聚合层不区分来源。三条路径在降级链中地位平等。输出已通过各层适配器归一化，调用方看到的是同一个格式。

---

## 四、选择指南

| 场景 | 方案 |
|------|------|
| 外部 API，需要自己写 handler | 开发 native 指令包（02 文档） |
| 已有 MCP Server | MCP bridge 自动编译 |
| ClawHub 有现成 skill | skill bridge + 路由 + 适配器 |
| 非代码经验 | nocode 指令包（03 文档） |
