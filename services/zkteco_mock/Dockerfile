FROM python:3.12-slim

WORKDIR /app

COPY server.py /app/server.py

ENV ZKTECO_HOST=0.0.0.0 \
    ZKTECO_PORT=8090 \
    ZKTECO_DB_PATH=/data/zkteco_mock.db \
    ZKTECO_SEED_MONTH=2026-07

VOLUME ["/data"]
EXPOSE 8090

CMD ["python", "/app/server.py"]
