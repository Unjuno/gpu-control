FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt requirements-test.txt requirements-worker.txt ./
RUN pip install --no-cache-dir -r requirements.txt
RUN useradd --uid 10001 --create-home gateway

COPY gpu_gateway ./gpu_gateway
COPY app.py ./app.py

USER gateway

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
