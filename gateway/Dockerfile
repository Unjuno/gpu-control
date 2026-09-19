FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt requirements-test.txt requirements-worker.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY gpu_gateway ./gpu_gateway
COPY app.py ./app.py

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
