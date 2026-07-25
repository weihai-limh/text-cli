FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data

# A5 endpoint gateway — sits between callers and A3/A9 backends
EXPOSE 29050

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "29050"]
