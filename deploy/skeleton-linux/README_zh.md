# skeleton-linux

> **此目录由构建脚本自动填充，请勿手动编辑。**

Linux 部署包由 `scripts/release/ubuntu/build.py` 按 `VERSION` 自动生成。需要发布时运行对应脚本：

```bash
# Ubuntu/Debian 包
python scripts/release/ubuntu/build.py --version 0.1.1
```

生成的制品将存放在 `deploy/skeleton-linux/` 下。
