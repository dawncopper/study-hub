# StudyHub 学习小站 - 后端镜像（Python 3.12 slim）
FROM python:3.12-slim

# Tesseract OCR 及中文字体（错题 OCR / PDF 中文导出）
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-chi-sim \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai

WORKDIR /app

# 先装依赖（利用缓存层）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目
COPY app ./app
COPY README.md ./

# 数据目录（SQLite / 上传图 / PDF 导出）
RUN mkdir -p /app/data/uploads /app/data/exports
VOLUME ["/app/data"]

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
