# 2hao-analyst 运行镜像（R78 CI/CD 骨架）
FROM python:3.10-slim

WORKDIR /app

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    git fontconfig fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 应用
COPY . .
RUN mkdir -p data output logs

# 非 root 运行
RUN useradd -m analyst
USER analyst

ENV PYTHONPATH=/app
CMD ["python", "main.py", "--help"]
