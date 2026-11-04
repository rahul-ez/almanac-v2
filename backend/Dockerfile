FROM python:3.13-slim
WORKDIR /workspace/backend
COPY backend/requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir -r /tmp/requirements.lock
ENV PYTHONPATH=/workspace/backend PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY . /workspace
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
