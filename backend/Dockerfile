FROM node:24-alpine AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim
WORKDIR /workspace/backend
COPY backend/requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir -r /tmp/requirements.lock
ENV PYTHONPATH=/workspace/backend PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY . /workspace
COPY --from=frontend /frontend/dist /opt/almanac-frontend
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
