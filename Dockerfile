FROM node:22-bookworm-slim AS frontend
WORKDIR /build/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml requirements.lock ./
COPY backend/ backend/
RUN pip install --no-cache-dir -r requirements.lock && pip install --no-cache-dir --no-deps . && useradd --create-home app
COPY config/ config/
COPY migrations/ migrations/
COPY alembic.ini ./
COPY --from=frontend /build/frontend/dist frontend/dist/
USER app
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn backend.api:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
