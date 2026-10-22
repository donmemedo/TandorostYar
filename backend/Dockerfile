# syntax=docker/dockerfile:1
# Base images are pinned by digest; Dependabot/Renovate bumps them. Dependencies install with --require-hashes.
FROM python:3.12-slim-bookworm@sha256:6a0e06f5ba0b373d051aabd3fffb9b873f27f9a2a3a14bcbe37dee6f0e3bbc70 AS build
WORKDIR /w
COPY requirements.txt .
# retry: flaky networks drop DNS mid-install; the cache keeps finished downloads
RUN python -m venv /opt/venv && \
    for _ in 1 2 3 4 5 6; do /opt/venv/bin/pip install --no-cache-dir --retries 10 --timeout 60 --require-hashes -r requirements.txt && break; sleep 10; done; \
    /opt/venv/bin/python -c "import fastapi, uvicorn, zoneinfo; zoneinfo.ZoneInfo('Asia/Tehran')"

FROM python:3.12-slim-bookworm@sha256:6a0e06f5ba0b373d051aabd3fffb9b873f27f9a2a3a14bcbe37dee6f0e3bbc70
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH=/opt/venv/bin:$PATH DB_PATH=/data/pact.db HOST=0.0.0.0 PORT=8000
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin app && mkdir /data && chown 10001:10001 /data
COPY --from=build /opt/venv /opt/venv
WORKDIR /app
COPY app ./app
USER 10001:10001
VOLUME /data
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=4s --start-period=40s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"]
# `python -m app` pins the safe uvicorn settings (no proxy-header rewriting, one worker, bounded concurrency): see app/__main__.py
CMD ["python", "-m", "app"]
