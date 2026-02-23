FROM python:3.13-slim

WORKDIR /app

# 複製 requirements 並安裝
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製所有程式碼
COPY . .

# 建立 docs 目錄
RUN mkdir -p docs/sops docs/reports

# 預設 Web 模式
EXPOSE 8000

# 環境變數（可由 .env 或 docker-compose 覆蓋）
ENV PYTHONUNBUFFERED=1

# 啟動命令（可切換為 CLI 模式）
# Web: uvicorn web.app:app --host 0.0.0.0 --port 8000
# CLI: python main.py
CMD ["uvicorn", "web.app:app", "--host", "0.0.0.0", "--port", "8000"]
