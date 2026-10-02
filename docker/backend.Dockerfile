# API and pipeline image. Build from the repository root:
#   docker build -f docker/backend.Dockerfile -t observatory-backend .
# INSTALL_ML=false gives a small image that runs with the deterministic fallback NLP
# (useful for the API alone); the daily pipeline should use INSTALL_ML=true.
FROM python:3.11-slim AS base

ARG INSTALL_ML=true
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app/backend \
    HF_HOME=/models

WORKDIR /app
COPY pyproject.toml README.md ./
COPY backend ./backend
COPY database ./database

# CPU-only torch keeps the image ~1.5 GB smaller than the default CUDA wheels.
RUN if [ "$INSTALL_ML" = "true" ]; then \
      pip install --extra-index-url https://download.pytorch.org/whl/cpu ".[ml,llm]"; \
    else \
      pip install ".[llm]"; \
    fi

RUN useradd --create-home --uid 10001 app && mkdir -p /models && chown app /models
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"

CMD ["uvicorn", "observatory.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
