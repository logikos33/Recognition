FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

RUN groupadd -r epi && useradd -r -g epi -m epi

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chown -R epi:epi /app
USER epi

EXPOSE ${PORT:-8006}
CMD ["python", "-m", "scheduler.main"]
