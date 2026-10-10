# syntax=docker/dockerfile:1
# ResumeLens backend: multi-stage build, CPU-only torch, models baked into the image.

ARG PYTHON_IMAGE=python:3.11-slim

# ---------------------------------------------------------------- builder stage
FROM ${PYTHON_IMAGE} AS builder

ARG EMBEDDING_MODEL=all-MiniLM-L6-v2
ARG SPACY_MODEL_WHEEL=https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    HF_HOME=/opt/models \
    SENTENCE_TRANSFORMERS_HOME=/opt/models

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv && pip install --upgrade pip==24.3.1

WORKDIR /build
COPY requirements.txt .

# CPU-only torch first (~200 MB instead of the ~2.5 GB CUDA build), then the rest.
RUN pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu \
    && pip install -r requirements.txt \
    && pip install "${SPACY_MODEL_WHEEL}"

# Pre-download the embedding model so the first request does not wait for it.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('${EMBEDDING_MODEL}', device='cpu', cache_folder='/opt/models')"

# ---------------------------------------------------------------- runtime stage
FROM ${PYTHON_IMAGE} AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    HF_HOME=/opt/models \
    SENTENCE_TRANSFORMERS_HOME=/opt/models \
    MODEL_CACHE_DIR=/opt/models \
    DATABASE_URL=sqlite:////app/data/resumelens.db \
    TOKENIZERS_PARALLELISM=false

RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home-dir /app --shell /usr/sbin/nologin app

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder --chown=app:app /opt/models /opt/models

WORKDIR /app
COPY --chown=app:app app ./app
RUN mkdir -p /app/data && chown app:app /app/data

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=4).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers"]
