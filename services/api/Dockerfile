##############################################################################
# Recognition Platform — API Backend Dockerfile
# Build context: repo root (dockerfilePath = "services/api/Dockerfile")
# Sem torch/ultralytics — API leve (~500MB)
##############################################################################
FROM python:3.11-slim

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Non-root user
RUN groupadd -r epi && useradd -r -g epi -m epi

WORKDIR /app

# Install deps from requirements/api.txt
COPY requirements/ requirements/
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements/api.txt

# Copy app code and startup script
COPY railway_start.py .
COPY services/api/ .
COPY infra/migrations/ infra/migrations/

# Permissions
RUN chown -R epi:epi /app
USER epi

ENV PYTHONUNBUFFERED=1

EXPOSE ${PORT:-8080}

CMD ["python3", "railway_start.py"]
