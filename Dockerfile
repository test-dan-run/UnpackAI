# syntax=docker/dockerfile:1
#
# The UnpackAI server image. The build context is the repository root, because
# the server serves index.html and reads the skills in .claude/skills at run
# time. The layout inside the image matches the repository:
#
#   /app/index.html
#   /app/.claude/skills/...
#   /app/server/unpackai_server/...
#
# Targets:
#   runtime  the server (the default)
#   test     the server tests

ARG PYTHON_IMAGE=python:3.13-slim

FROM ${PYTHON_IMAGE} AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
RUN groupadd --system --gid 10001 unpackai \
 && useradd --system --uid 10001 --gid unpackai --home-dir /app --shell /usr/sbin/nologin unpackai
WORKDIR /app/server
COPY server/requirements.txt ./
RUN pip install -r requirements.txt
COPY index.html /app/index.html
COPY .claude/skills /app/.claude/skills
COPY server/unpackai_server ./unpackai_server

FROM base AS test
COPY server/requirements-dev.txt server/pytest.ini ./
RUN pip install -r requirements-dev.txt
COPY server/tests ./tests
USER unpackai
CMD ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider"]

FROM base AS runtime
# The database lives on a volume at /data. The API key comes from the Docker
# secret at /run/secrets/anthropic_api_key, never from an environment variable.
ENV UNPACKAI_DB=/data/unpackai.sqlite3 \
    UNPACKAI_SECRET_SOURCE=docker-secret
RUN mkdir -p /data && chown unpackai:unpackai /data
VOLUME ["/data"]
USER unpackai
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"]
# Inside the container the server listens on every interface, so Docker can
# forward the port. compose.yaml publishes it on 127.0.0.1 of the host only.
CMD ["python", "-m", "unpackai_server", "--host", "0.0.0.0", "--port", "8000"]
