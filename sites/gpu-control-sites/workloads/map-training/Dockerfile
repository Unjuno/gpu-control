ARG PYTHON_BASE
FROM ${PYTHON_BASE}
ARG MAP_SOURCE_SHA
LABEL org.opencontainers.image.source="https://github.com/Unjuno/model-as-a-paper" \
      org.opencontainers.image.revision="${MAP_SOURCE_SHA}"
WORKDIR /opt/map
RUN python -m pip install --no-cache-dir 'torch==2.10.0' \
      --index-url https://download.pytorch.org/whl/cu128 \
    && python -m pip install --no-cache-dir 'numpy==2.2.6'
COPY source/src/model_as_a_paper /opt/map/src/model_as_a_paper
COPY source/configs/map44.json /opt/map/configs/map44.json
ENV PYTHONPATH=/opt/map/src \
    PYTHONDONTWRITEBYTECODE=1 \
    MAP_IMAGE_SOURCE_SHA=${MAP_SOURCE_SHA}
