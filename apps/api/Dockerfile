# Build from the apps/api directory:
#   docker build -t lexa-api:local apps/api
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install the declared API dependencies from the project's canonical metadata.
COPY pyproject.toml ./
COPY app ./app
RUN python -m pip install --no-cache-dir . \
    && useradd --create-home --uid 10001 --shell /usr/sbin/nologin lexa \
    && chown -R lexa:lexa /app

USER 10001:10001
EXPOSE 8000

# Keep the container health endpoint dependency-free. Full dependency readiness
# remains available at /ready and is used by Kubernetes readiness probes.
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:' + __import__('os').getenv('PORT', '8000') + '/health', timeout=2)" || exit 1

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
