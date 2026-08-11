# skeleton-win

> **此目录由构建脚本自动填充，请勿手动编辑。**

Windows 部署包由 `scripts/release/win/build.py` 按 `VERSION` 自动生成。需要发布时运行对应脚本：

```bash
# Windows 包
python scripts/release/win/build.py --version 0.1.1
```

生成的制品将存放在 `deploy/skeleton-win/` 下。
