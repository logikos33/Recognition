FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    curl \
    git \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 preannot
USER preannot
WORKDIR /app

COPY --chown=preannot:preannot requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

COPY --chown=preannot:preannot src/ ./src/

HEALTHCHECK --interval=30s --timeout=30s --start-period=120s \
    CMD curl -f http://localhost:${PORT:-8080}/health || exit 1

ENV PATH="/home/preannot/.local/bin:${PATH}"
CMD ["gunicorn", "-w", "1", "-b", "0.0.0.0:8080", "--timeout", "300", "src.main:app"]
