# 指令包转化器（脚手架生成器）

> 这三个脚本将既有软件工程制品转化为指令包 **起手骨架**——不是完美的代码生成器，而是模板填充器。

所有转化器输出的是：
- 标准的目录结构
- `schema.json` 模板（含元数据和指令声明）
- `handler.py` 桩代码（含函数签名和注册装饰器）

**拿到骨架后，你或 AI 还需要**：
- 填写实际的业务逻辑
- 配置 API key 和凭证
- 补充降级和错误处理
- 本地 `text-cli;install` 自测

完整开发流程请参考 [指令包开发指南](../docs/package-dev-guide_zh.md)。

## 三个转化器

| 脚本 | 输入 | 输出骨架类型 |
|------|------|-------------|
| `postman_to_pkg.py` | Postman Collection JSON | webapi 指令包 |
| `readme_to_pkg.py` | 结构化 Markdown（符合 nocode 格式） | nocode 指令包 |
| `mcp_to_pkg.py` | MCP server（`mcporter list --json`） | MCP 桥接包 |
