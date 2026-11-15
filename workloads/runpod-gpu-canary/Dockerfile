FROM runpod/pytorch@sha256:0a360022e8de4375af99430f84e8b38951acc397252163a37ceac7204d01be35

ARG SOURCE_REPOSITORY
ARG SOURCE_REVISION
LABEL org.opencontainers.image.source="https://github.com/Unjuno/gpu-control" \
      org.opencontainers.image.revision="${SOURCE_REVISION}" \
      io.gpu-control.workload="tiny-gpu-training-v1"

RUN useradd --no-create-home --uid 10001 --shell /usr/sbin/nologin workload
WORKDIR /opt/gpu-control
COPY --chmod=0555 workloads/runpod-gpu-canary/idle.py /opt/gpu-control/idle
COPY --chmod=0555 workloads/runpod-gpu-canary/run_registered_workload.py /opt/gpu-control/run-registered-workload
COPY --chmod=0444 workloads/tiny-lm/tiny_lm.py /opt/gpu-control/tiny_lm.py

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
ENTRYPOINT ["/opt/gpu-control/idle"]
