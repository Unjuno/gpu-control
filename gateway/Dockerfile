FROM python:3.12-slim

WORKDIR /app/gateway

COPY gateway/requirements.txt gateway/requirements-test.txt gateway/requirements-worker.txt ./
COPY pyproject.toml README.md /app/
COPY src/ /app/src/
RUN pip install --no-cache-dir -r requirements.txt
RUN useradd --uid 10001 --create-home gateway

COPY gateway/gpu_gateway ./gpu_gateway
COPY gateway/app.py ./app.py

USER gateway

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
