##############################################################################
# EPI Monitor V2 — Backend Dockerfile
# Usado por API e Worker (mesmo container, comando diferente no Railway)
##############################################################################
FROM python:3.11-slim AS base

# System dependencies: FFmpeg, OpenCV libs, git
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Non-root user
RUN groupadd -r epi && useradd -r -g epi -m epi

WORKDIR /app

# Dependencies first (cache layer)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Pre-download YOLOv8 weights (evita download em runtime ~500MB)
RUN python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')" || true

# Copy app code
COPY . .

# Permissions
RUN chown -R epi:epi /app
USER epi

# Port via Railway env var (não hardcoded)
EXPOSE ${PORT:-5001}

# Default: API server (worker sobrescreve no railway.toml)
CMD ["gunicorn", \
     "-w", "2", \
     "-k", "eventlet", \
     "--worker-connections", "1000", \
     "--timeout", "120", \
     "--bind", "0.0.0.0:${PORT:-5001}", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "app:create_app()"]
