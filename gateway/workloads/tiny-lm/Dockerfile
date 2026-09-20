# CPU correctness fixture. CI records the resolved image ID; this tag is not a digest lock.
FROM python:3.12-slim-bookworm
WORKDIR /work
COPY tiny_lm.py /work/tiny_lm.py
USER 10001:10001
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
ENTRYPOINT ["python", "-I", "/work/tiny_lm.py"]
