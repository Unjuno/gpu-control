"""Legacy FastAPI entrypoint, retained for local compatibility tests only."""
from gpu_gateway.app import create_app
from gpu_gateway.ci_routes import install_ci_routes

app = create_app()
install_ci_routes(app)
