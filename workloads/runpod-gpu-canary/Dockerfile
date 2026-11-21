FROM nvidia/cuda@sha256:0f6bfcbf267e65123bcc2287e2153dedfc0f24772fb5ce84afe16ac4b2fada95

ARG SOURCE_REPOSITORY
ARG SOURCE_REVISION
LABEL org.opencontainers.image.source="https://github.com/Unjuno/gpu-control" \
      org.opencontainers.image.revision="${SOURCE_REVISION}" \
      io.gpu-control.workload="runpod-gpu-canary-v1"

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install --yes --no-install-recommends python3-minimal python3-pip \
    && python3 -m pip install --no-cache-dir runpod==2.4.0 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --no-create-home --uid 10001 --shell /usr/sbin/nologin workload
WORKDIR /opt/gpu-control
COPY --chmod=0555 workloads/runpod-gpu-canary/idle.py /opt/gpu-control/idle
COPY --chmod=0555 workloads/runpod-gpu-canary/run_registered_workload.py /opt/gpu-control/run-registered-workload
COPY --chmod=0555 workloads/runpod-gpu-canary/gpu_probe.py /opt/gpu-control/gpu_probe.py
COPY --chmod=0555 workloads/runpod-gpu-canary/serverless_handler.py /opt/gpu-control/serverless_handler.py

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
ENTRYPOINT ["python3", "/opt/gpu-control/serverless_handler.py"]
