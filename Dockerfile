FROM node:20-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    ATULYA_HOST=0.0.0.0 \
    ATULYA_PORT=8501

WORKDIR /app
RUN apt-get update && \
    apt-get install -y --no-install-recommends libsndfile1 ffmpeg && \
    rm -rf /var/lib/apt/lists/*

COPY . .
COPY --from=web /web/dist ./web/dist
RUN pip install -e ".[serve]"

VOLUME /app/data
EXPOSE 8501
CMD ["python", "-m", "atulya.sevak"]
