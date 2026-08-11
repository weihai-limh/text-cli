# text-cli v{VERSION} 部署核对清单

## 初次配置

启动脚本会自动完成以下初始化，你也可以手动操作。

- [ ] 复制 `copilot/auxiliary_config.example.json` → `auxiliary_config.json`，按需编辑（字段含义见使用手册附录）
- [ ] 设置 `TEXT_CLI_PACKAGE_SOURCE_DIRS` 环境变量（指向指令包目录，install/co-install 时搜索包用）
- [ ] （A5 endpoint）编辑 `A3_BACKENDS` 列表，填入后端 service 地址
- [ ] （A5 endpoint）可选：配置 `ADMIN_API_KEY` 启用管理 API

## 所有分发包通用

- [ ] Python 3.10+ 已安装（`python --version`）
- [ ] pip 可用（`pip --version`）
- [ ] 启动脚本运行无报错（Windows: 双击 start.bat / Linux: ./start.sh）
- [ ] 防火墙允许所需端口

## A2 copilot

- [ ] curl http://127.0.0.1:20260/text-cli/health → 200

## A3+ service（service/ 文件夹存在时）

- [ ] 端口 28050 未被占用
- [ ] curl http://localhost:28050/text-cli/health → 200
- [ ] curl -X POST http://localhost:28050/text-cli/cli -H "Content-Type: application/json" -d '{"prompt":"AI:text-cli;query"}' → 返回指令列表

## A5 endpoint（start-endpoint 启动脚本存在时）

- [ ] 端口 29050 未被占用
- [ ] curl http://localhost:29050/health → 200

## 停止服务

```
Windows: taskkill /F /IM python.exe
Linux:   pkill -f "python.*main.py"
```

也可以直接关闭启动脚本对应的终端窗口。
