# ─────────────────────────────────────────────────────────────────────────────
# Stage 1 — build the frontend (Vite) from source.
# This guarantees the dist/ that ends up in the image is always derived from
# the current frontend/ tree, not from whatever happened to be on the
# developer's laptop when they zipped the project up.
# ─────────────────────────────────────────────────────────────────────────────
FROM node:20-slim AS frontend-builder

WORKDIR /app/frontend

# npmjs.org egress from Tencent Cloud mainland regions is flaky; use the
# domestic mirror to make CI builds deterministic.
RUN npm config set registry https://registry.npmmirror.com

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build
# → produces /app/frontend/dist/

# ─────────────────────────────────────────────────────────────────────────────
# Stage 2 — python runtime + FastAPI app.
# Copies the freshly-built dist/ from stage 1 so the Python image never has
# to trust the host machine's dist/ state.
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libheif-dev libjpeg-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source. frontend/dist/ is excluded via .dockerignore so the host
# copy never shadows the stage-1 build.
COPY . .

# Overlay the freshly-built frontend bundle.
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

ENV PORT=80
EXPOSE 80

CMD uvicorn api.app:app --host 0.0.0.0 --port ${PORT}
