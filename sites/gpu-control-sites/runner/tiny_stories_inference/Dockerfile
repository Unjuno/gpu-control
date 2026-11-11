ARG PYTHON_BASE=python:3.12-slim-bookworm@sha256:6dd8b6dab6b3adc7812bab69eca5dbdc1a5cc690ad28306d234ffb4ef8ac9753
FROM ${PYTHON_BASE} AS build
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /build
COPY runner/third_party/llama2.c/run.c /build/run.c
RUN printf '%s  %s\n' '78951c4623437da86cc5d835ea26af8c750c5132dfeb6e506c4a2db918e61682' /build/run.c | sha256sum -c -
RUN gcc -O2 -fno-strict-aliasing -Werror=implicit-function-declaration /build/run.c -lm -o /build/run
RUN curl --fail --location --silent --show-error \
      https://huggingface.co/karpathy/tinyllamas/resolve/0bd21da7698eaf29a0d7de3992de8a46ef624add/stories15M.bin \
      -o /build/stories15M.bin \
    && printf '%s  %s\n' 'cd590644d963867a2b6e5a1107f51fad663c41d79c149fbecbbb1f95fa81f49a' /build/stories15M.bin | sha256sum -c -
RUN curl --fail --location --silent --show-error \
      https://raw.githubusercontent.com/karpathy/llama2.c/350e04fe35433e6d2941dce5a1f53308f87058eb/tokenizer.bin \
      -o /build/tokenizer.bin \
    && printf '%s  %s\n' '50a52ef822ee9e83de5ce9d0be0a025a773d019437f58b5ff9dcafb063ece361' /build/tokenizer.bin | sha256sum -c -

FROM ${PYTHON_BASE} AS runtime
ARG SOURCE_REPOSITORY
ARG SOURCE_SHA
LABEL org.opencontainers.image.source="${SOURCE_REPOSITORY}" \
      org.opencontainers.image.revision="${SOURCE_SHA}" \
      org.opencontainers.image.title="gpu-control-tiny-stories-inference"
WORKDIR /work
COPY --from=build /build/run /work/run
COPY --from=build /build/stories15M.bin /work/stories15M.bin
COPY --from=build /build/tokenizer.bin /work/tokenizer.bin
COPY runner/tiny_stories_inference/inference.py /work/inference.py
USER 10001:10001
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
ENTRYPOINT ["python", "-I", "/work/inference.py"]
