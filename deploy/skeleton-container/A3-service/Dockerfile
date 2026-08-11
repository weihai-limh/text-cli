FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 代码默认端口 main.py:618 PORT=28050（修正原 8000 写死；
# 8000 会让容器内监听与协议链/MCP 脱节）
EXPOSE 28050

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "28050"]
