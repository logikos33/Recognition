FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -r epi && useradd -r -g epi -m epi

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Pré-download do modelo YOLO no build (evita download em runtime)
# || true: falha silenciosa se rede indisponível — baixa em runtime
RUN python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')" || true

COPY . .
RUN chown -R epi:epi /app
USER epi

EXPOSE ${PORT:-8002}
CMD ["python", "-m", "inference.main"]
