# syntax=docker/dockerfile:1
FROM eclipse-temurin:21-jdk-jammy AS smoke
WORKDIR /probe
COPY tools/SmokeCheck.java .
RUN javac --release 17 SmokeCheck.java
USER 10001:10001
ENTRYPOINT ["java", "SmokeCheck"]

FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home --uid 10001 panoraiq
COPY --chown=panoraiq:panoraiq panoraiq ./panoraiq
RUN mkdir /app/instance && chown panoraiq:panoraiq /app/instance
USER panoraiq
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3)"
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--access-logfile", "-", "--error-logfile", "-", "panoraiq:create_app()"]

FROM runtime AS test
USER root
COPY requirements-dev.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY --chown=panoraiq:panoraiq tests ./tests
COPY --chown=panoraiq:panoraiq scripts ./scripts
COPY --chown=panoraiq:panoraiq infra ./infra
USER panoraiq
CMD ["python", "-m", "pytest", "--junitxml=/results/junit.xml", "--cov=panoraiq", "--cov-report=term-missing", "--cov-report=xml:/results/coverage.xml", "-o", "cache_dir=/tmp/pytest-cache"]
