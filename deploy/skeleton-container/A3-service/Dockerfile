# =========================================================================
# text-cli A3-service 沙箱启动器镜像（薄沙箱统一方案，2026-08-14 回灌）
# A3 = copilot(A2) 累积 + service(A3) 基础 —— 同容器融合。
# 定位：容器 = 沙箱 + 启动器。镜像只含 Python 环境 + 依赖 + 代码种子。
# 运行时代码 bake 到 /app/seed/，首次运行由 entrypoint 吐到 /app/runtime/（外挂点）。
# 代码/包/数据全部外挂宿主机 —— 频繁装包、热更新不 rebuild。
#
# 源策略（lemondy 2026-08-14）：标准发行镜像用【官方源】。
# =========================================================================
FROM python:3.13-slim

# 系统依赖
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    curl git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 依赖分层缓存（先装依赖）
# requirements 已根修 fastapi>=0.136,<1 / uvicorn>=0.47（兼容 starlette 1.x）
COPY service/requirements.txt /tmp/service-requirements.txt
RUN pip install --no-cache-dir -r /tmp/service-requirements.txt \
    && pip install --no-cache-dir fastmcp requests

# 环境变量（沙箱级默认；运行时 PYTHONPATH 由 entrypoint 按外挂点重设）
ENV PYTHONUNBUFFERED=1

# ── 代码种子（bake 到 /app/seed/，首次运行吐到外挂的 /app/runtime/）──
# 含 copilot(A2) + service(A3) 两个运行时
COPY copilot/   /app/seed/copilot/
COPY service/   /app/seed/service/

# ── 随包分发三类文件（标准发行镜像：手册 + 标准包 + SDK）──
COPY docs/       /app/docs/
COPY packages/   /packages/
COPY protocol/   /app/protocol/

# 种子归 UID 1001（宿主运行用户）所有
RUN chown -R 1001:1001 /app/seed

# 外挂点：/app/runtime（代码，首次由 seed 填充），/app/data（sqlite 等）
RUN mkdir -p /app/runtime /app/data && chown 1001:1001 /app/runtime /app/data

# 端口：service（能力面）
# copilot(20260) 绑 127.0.0.1，仅回环可达，不 EXPOSE
EXPOSE 28050

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:28050/text-cli/health || exit 1

# 入口脚本：首次吐代码 → 启动 copilot → service
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
