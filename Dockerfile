# ── Stage 1: Build React ──────────────────────────────────────────────────────
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm install --silent

COPY frontend/ ./
# In produzione l'API è sullo stesso dominio — nessun URL hardcoded necessario
ENV NODE_ENV=production
RUN npm run build

# ── Stage 2: Python backend ───────────────────────────────────────────────────
FROM python:3.11-slim
WORKDIR /app

# Dipendenze Python
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Codice backend
COPY backend/ ./

# React build → /app/static (FastAPI la servirà da lì)
COPY --from=frontend-build /app/frontend/build ./static

# Directory per DB e log (Railway usa volume persistente tramite env DB_PATH)
RUN mkdir -p /data /app/logs

# Porta esposta da Railway
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
