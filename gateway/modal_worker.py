"""Optional Modal CPU worker deployment. Deploying activates billable CPU scheduling.

Do not import this file as the Vercel app. Run manually from gateway/ only after
creating the database schema and the operator-owned gpu-control-worker Secret.
The Secret contains gateway DB/settings. Provider credentials stay off the Web app.
"""
from pathlib import Path
import time
import modal

ROOT = Path(__file__).parent
app = modal.App('gpu-control-worker')
image = (modal.Image.debian_slim(python_version='3.12')
         .pip_install_from_requirements(str(ROOT / 'requirements-worker.txt'))
         .add_local_python_source('gpu_gateway'))


@app.function(image=image, secrets=[modal.Secret.from_name('gpu-control-worker')],
              schedule=modal.Period(seconds=60), timeout=55, cpu=0.25,
              memory=512, max_containers=1)
def drain():
    from gpu_gateway.backends import build_backends
    from gpu_gateway.config import Settings
    from gpu_gateway.store import Store
    from gpu_gateway.worker import Worker
    settings = Settings.from_env()
    worker = Worker(Store(settings.database_url), settings, build_backends(settings))
    # No HTTP request is held open. DB leases protect against overlapping invocations.
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        worker.tick()
        time.sleep(3)
