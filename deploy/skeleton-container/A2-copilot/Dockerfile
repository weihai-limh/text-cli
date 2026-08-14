# =========================================================================
# text-cli A2-copilot 沙箱启动器镜像（薄沙箱统一方案，2026-08-14 回灌）
# 定位：容器 = 沙箱 + 启动器。代码 bake 到 /app/seed，首次运行吐到外挂点 /app/runtime。
# copilot 仅依赖标准库 + 内部模块（core/handlers），无需 pip install。
#
# 设计红线：copilot 仅本机可达(127.0.0.1:20260)，【绝不 -p 20260:20260 暴露 0.0.0.0】。
#   运行时用 --network=host，让本机 AI 经回环 localhost:20260 调用。
#   无 token 由 127.0.0.1 安全边界兜底（text-cli-copilot.py:73）。
#
# 源策略（lemondy 2026-08-14）：标准发行镜像用【官方源】。
# =========================================================================
FROM python:3.13-slim

# 系统依赖
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PYTHONUNBUFFERED=1

# ── 代码种子（bake 到 /app/seed/，首次运行吐到外挂的 /app/runtime/）──
COPY copilot/   /app/seed/copilot/

# ── 随包分发三类文件（标准发行镜像：手册 + 标准包 + SDK）──
COPY docs/       /app/docs/
COPY packages/   /packages/
COPY protocol/   /app/protocol/

# 种子归 UID 1001（宿主运行用户）所有
RUN chown -R 1001:1001 /app/seed

# 外挂点：/app/runtime（代码，首次由 seed 填充）
RUN mkdir -p /app/runtime && chown 1001:1001 /app/runtime

# copilot 绑 127.0.0.1，红线不 EXPOSE 0.0.0.0；用 --network=host + 回环可达
# 不加 EXPOSE 20260（避免暗示可 -p 暴露）

# 健康检查：经 host 网络回环探测
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://127.0.0.1:20260/text-cli/health || exit 1

# 入口脚本：首次吐代码 → 启动 copilot
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
