##############################################################################
# EPI Monitor V2 — Frontend Dockerfile
# Build context: frontend/ (Railway root directory = frontend/)
##############################################################################

FROM node:22-alpine AS build

WORKDIR /app

# Copy package files + .npmrc (legacy-peer-deps for vanilla-extract)
COPY package.json package-lock.json* .npmrc* ./
RUN npm install --legacy-peer-deps

# Copy source
COPY . .

# Build args for API URL
ARG VITE_API_URL
ARG VITE_WS_URL
ENV VITE_API_URL=${VITE_API_URL}
ENV VITE_WS_URL=${VITE_WS_URL}

# Build
RUN npm run build

# Serve with Python
FROM python:3.11-alpine

WORKDIR /app
COPY --from=build /app/dist ./dist
COPY serve.py ./serve.py

EXPOSE ${PORT:-3000}

CMD ["python3", "serve.py"]
