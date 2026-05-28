# Worker On-Premise — EPI Monitor V2
# Base image: Python 3.11 slim + NVIDIA CUDA (para inferência com GPU)
FROM python:3.11-slim

# Dependências do sistema (FFmpeg + OpenCV + PostgreSQL client)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instalar dependências Python (apenas worker — inclui torch + ultralytics)
COPY ../requirements/worker.txt requirements/worker.txt
RUN pip install --no-cache-dir -r requirements/worker.txt

# Copiar código da aplicação
COPY ../app ./app
COPY ../railway_start.py ./railway_start.py

# Variável de ambiente que identifica este container como worker on-premise
ENV WORKER_TYPE=onpremise
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Celery worker: consome fila inference_{TENANT_SCHEMA} + filas padrão
ENTRYPOINT ["sh", "-c", \
    "celery -A app.infrastructure.queue.celery_app:celery worker \
    --loglevel=info \
    --concurrency=4 \
    --queues=inference_${TENANT_SCHEMA},inference,training,extraction \
    --hostname=worker-onpremise-${TENANT_SCHEMA}@%h"]
