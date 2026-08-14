# =========================================================================
# text-cli A9 沙箱启动器镜像（方案定型 2026-08-13，回灌真源 2026-08-14）
# 定位：容器 = 沙箱 + 启动器。镜像只含 Python 环境 + 依赖 + 代码种子。
# 运行时代码 bake 到 /app/seed/，首次运行由 entrypoint 吐到 /app/runtime/（外挂点）。
# 代码/包/数据全部外挂宿主机 —— 频繁装包、热更新不 rebuild。
#
# 源策略（lemondy 2026-08-14）：标准发行镜像用【官方源】。
#   华为/清华源是家庭内网(DMZ)私有部署环境的网络特例，不属标准发行品。
# =========================================================================
FROM python:3.13-slim

# 系统依赖 —— python:3.13-slim 是 Debian bookworm
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    curl git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 依赖分层缓存（先装依赖）
# 版本校准：requirements 已根修 fastapi>=0.136,<1 / uvicorn>=0.47（对齐生产 .151），
# 兼容 fastmcp 拉起的 starlette 1.x，避免 on_startup 崩溃。
COPY service/requirements.txt /tmp/service-requirements.txt
RUN pip install --no-cache-dir -r /tmp/service-requirements.txt \
    && pip install --no-cache-dir "fastapi>=0.136,<1" "uvicorn>=0.47" fastmcp requests

# 环境变量（沙箱级默认；运行时 PYTHONPATH 由 entrypoint 按外挂点重设）
ENV PYTHONUNBUFFERED=1

# ── 代码种子（bake 到 /app/seed/，首次运行吐到外挂的 /app/runtime/）──
# aggregate 已含在 service/aggregate（build_advanced 放入），随 service 一并 seed
COPY service/   /app/seed/service/
COPY copilot/   /app/seed/copilot/
COPY MCPservice/ /app/seed/mcp/

# ── 随包分发三类文件（标准发行镜像：手册 + 标准包 + SDK）──
COPY docs/       /app/docs/
COPY packages/   /packages/
COPY protocol/   /app/protocol/

# 种子归 UID 1001（宿主运行用户）所有——容器以 --user 1001 运行时能读/拷 seed，
# 外挂 runtime 文件归宿主用户可热更新。
RUN chown -R 1001:1001 /app/seed

# 外挂点：/app/runtime（代码，首次由 seed 填充），/app/data（sqlite 等）
RUN mkdir -p /app/runtime /app/data && chown 1001:1001 /app/runtime /app/data

# 端口：service（能力面） + MCP bridge（MCP 协议面）
# copilot(20260) 绑 127.0.0.1，仅内部 proxy 可达，不 EXPOSE
EXPOSE 28050 9020

# 健康检查：探测 service 的 /text-cli/health 端点
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:28050/text-cli/health || exit 1

# 入口脚本：首次吐代码 → 启动 copilot → MCP bridge → service
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
