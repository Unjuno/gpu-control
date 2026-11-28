"""Legacy FastAPI entrypoint, retained for local compatibility tests only."""
from gpu_gateway.app import create_app

app = create_app()
