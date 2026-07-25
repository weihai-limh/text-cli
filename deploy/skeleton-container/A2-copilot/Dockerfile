FROM python:3.13-slim

WORKDIR /app

# copilot 仅依赖标准库 + 内部模块 core/handlers，无需 pip install
COPY . .

# 设计红线(docs/product_zh.md P108): copilot 仅本机可达(127.0.0.1:20260)，
# 绝不映射 0.0.0.0。运行时用 --network=host，让本机 AI 经回环调用。
# 无 token 由 127.0.0.1 安全边界兜底（text-cli-copilot.py:73）。
EXPOSE 20260

CMD ["python", "text-cli-copilot.py"]
