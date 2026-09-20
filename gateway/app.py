"""Vercel/FastAPI entrypoint. Importing it does not create tables or GPU jobs."""
from gpu_gateway.app import create_app

app = create_app()
