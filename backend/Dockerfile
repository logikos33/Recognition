##############################################################################
# EPI Monitor V2 — API Backend Dockerfile
# Build context: repo root (dockerfilePath = "backend/Dockerfile")
# Sem torch/ultralytics — API leve (~500MB)
##############################################################################
FROM python:3.11-slim

# System deps (includes opencv deps for pre-annotation-service)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    ffmpeg \
    git \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Non-root user
RUN groupadd -r epi && useradd -r -g epi -m epi

WORKDIR /app

# Install deps — api.txt base + pre-annotation deps (torch, groundingdino, SAM)
# All services share this image; torch is needed by pre-annotation-service
COPY requirements/ requirements/
COPY pre-annotation-service/requirements.txt pre-annotation-requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements/api.txt \
    && pip install --no-cache-dir -r pre-annotation-requirements.txt

# Copy full repo structure (railway_start.py expects backend/ layout)
COPY railway_start.py .
COPY backend/ backend/
COPY migrations/ migrations/
COPY pre-annotation-service/ pre-annotation-service/

# Permissions
RUN chown -R epi:epi /app
USER epi

ENV PYTHONUNBUFFERED=1

EXPOSE ${PORT:-8080}

CMD ["python3", "railway_start.py"]
