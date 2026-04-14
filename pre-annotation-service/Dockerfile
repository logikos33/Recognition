FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    libgl1-mesa-glx \
    libglib2.0-0 \
    gcc \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 preannot
WORKDIR /app

# Install deps (build context = repo root)
COPY pre-annotation-service/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy service source
COPY pre-annotation-service/src/ ./src/

USER preannot

HEALTHCHECK --interval=30s --timeout=30s --start-period=120s \
    CMD curl -f http://localhost:${PORT:-8080}/health || exit 1

ENV PYTHONUNBUFFERED=1
ENV PATH="/home/preannot/.local/bin:${PATH}"

EXPOSE ${PORT:-8080}

CMD ["gunicorn", "-w", "1", "-b", "0.0.0.0:8080", "--timeout", "300", "--log-level", "info", "--access-logfile", "-", "src.main:app"]
