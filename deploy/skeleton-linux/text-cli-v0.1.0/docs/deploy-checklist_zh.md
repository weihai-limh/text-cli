# text-cli v0.1.0 部署核对清单

## 上线前

- [ ] Python 3.10+ 已安装（`python --version`）
- [ ] pip 可用（`pip --version`）
- [ ] 端口 20260、28050 未被其他进程占用
- [ ] `copilot/auxiliary_config.json` 已配置
- [ ] 防火墙规则允许 28050（如需局域网访问）

## 启动后

- [ ] `start.bat` 输出 "[OK] text-cli v0.1.0 部署成功！"
- [ ] `curl http://localhost:20260/text-cli/health` → 200
- [ ] `curl http://localhost:28050/text-cli/health` → 200
- [ ] `curl http://localhost:28050/text-cli/schema` → 返回指令列表
- [ ] 执行一条测试指令——`curl -X POST http://localhost:28050/text-cli/cli -H "Content-Type: application/json" -d "{\"directive\": \"AI:基础应用;天气查询,北京\"}"`

## 资源基线

| 项目 | 数值 |
|------|:---:|
| copilot 内存 | ~50 MB |
| service 内存 | ~80 MB |
| 磁盘占用 | ~15 MB（不含 pip 依赖） |
| Python 依赖 | httpx, fastapi, uvicorn, pydantic |

## 停止

关闭两个命令行窗口，或：

```bash
taskkill /F /IM python.exe
```
