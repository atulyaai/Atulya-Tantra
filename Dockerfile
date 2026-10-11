# Atulya server image (x86-64 and ARM64, e.g. NAS boxes and Raspberry Pi 4/5).
#   docker build -t atulya .
#   docker run -d --name atulya -p 127.0.0.1:8501:8501 --env-file .env \
#     -v atulya-data:/app/data -v atulya-models:/app/models atulya
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    ATULYA_CONTAINER=1 ATULYA_HOST=0.0.0.0 ATULYA_PORT=8501
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates libgomp1 curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 atulya
WORKDIR /app
COPY requirements.lock.txt ./
RUN python -m pip install -r requirements.lock.txt
COPY --chown=atulya:atulya . .
RUN mkdir -p data models && chown -R atulya:atulya data models
USER atulya
VOLUME ["/app/data", "/app/models"]
EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s \
    CMD curl -fsS -H "Host: localhost" http://127.0.0.1:8501/api/health || exit 1
# Bootstrap downloads models into the /app/models volume once, then serves.
CMD ["sh", "-c", "python tools/bootstrap.py && exec python -m atulya.cli serve"]
