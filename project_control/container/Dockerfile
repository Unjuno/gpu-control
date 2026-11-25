# The resolved image ID is recorded per check. This is NOT a reproducible digest lock.
# Only this control-plane Dockerfile is built; target Dockerfiles are never executed.
FROM python:3.12-slim-bookworm
WORKDIR /work
COPY run.py /work/run.py
COPY source/ /source/
USER 10001:10001
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
ENTRYPOINT ["python", "-I", "/work/run.py"]
