FROM python:3.13-slim

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 依赖分层缓存（先装依赖，后拷代码）
COPY service/requirements.txt /tmp/service-requirements.txt
RUN pip install --no-cache-dir -r /tmp/service-requirements.txt \
    && pip install --no-cache-dir fastmcp requests

# 三运行时源码
COPY service/   /app/service/
COPY copilot/   /app/copilot/
COPY MCPservice/ /app/mcp/
# 聚合路由表：aggregate/ 已在 service/ 内（由 build.py 放入），
# 随 service/ COPY 自动进入 /app/service/aggregate/
# service 通过 AGGREGATE_DIR=./aggregate（entrypoint.sh 设置）读取

# 环境变量
ENV PYTHONPATH=/app/service:/app/copilot:/app/mcp
ENV PYTHONUNBUFFERED=1

# 数据目录
RUN mkdir -p /app/data
VOLUME ["/app/data"]

# 端口：service（能力面） + MCP bridge（MCP 协议面）
# 20260（copilot）绑 127.0.0.1，仅内部 proxy 可达，不 EXPOSE
EXPOSE 28050 9020

# 健康检查：探测 service 的 /text-cli/health 端点
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:28050/text-cli/health || exit 1

# 入口脚本：启动 copilot → MCP bridge → service
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
