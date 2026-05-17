# A2 — Agent-Copilot 本地指令服务

部署在终端本地的指令代理。24 条本地指令 + CLI 命令引擎 + 路径引擎。

## Skill Bridge output_adapter

Skill Bridge 将 ClawHub 下载的 skill 桥接为 text-cli 指令。通用适配器做 status 归一化（baidumap: status 0 → ok），Provider 专用适配器做字段映射。

路由配置加 `output_adapter` 字段：

```json
{
  "skill-bdmap;geocode": {
    "adapter": "baidumap",
    "output_adapter": "baidu-map/geocode"
  }
}
```

骨架在通用适配器之后调用 output_adapter——不感知具体 provider，只从路由配置读取适配器路径并动态加载。

## adapters/ 目录

```
copilot/adapters/
  baidu-map/
    geocode.py    ← Baidu Agent Plan API → 规范 geocode 格式
```

每个 provider 一个子目录。output_adapter 的唯一职责：把 provider 专有输出格式映射到 text-cli 协议规范格式。

适配器 = `normalize(raw: dict) → dict`。输入是通用适配器处理后的结果，输出是规范格式。
