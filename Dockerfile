# MedGuard Explorer as a public demo: build the front end, then serve it with the Python API.
# Used by the Hugging Face Space (see deploy/space-README.md) and any Docker host.

FROM node:20-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MEDGUARD_PUBLIC=1 \
    MEDGUARD_HOST=0.0.0.0 \
    PORT=7860
RUN useradd --create-home --uid 1000 medguard
WORKDIR /app
COPY requirements-explorer.txt ./
RUN pip install --no-cache-dir -r requirements-explorer.txt
COPY src/ ./src/
COPY data/synthetic/ ./data/synthetic/
COPY --from=frontend /app/frontend/dist ./frontend/dist
USER medguard
EXPOSE 7860
CMD ["python", "src/explorer/server.py"]
