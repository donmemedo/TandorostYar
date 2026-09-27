FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
# retry: flaky networks drop DNS mid-install; the cache keeps finished downloads
RUN --mount=type=cache,target=/root/.cache/pip \
    for i in 1 2 3 4 5 6; do pip install --retries 10 --timeout 60 -r requirements.txt && break; sleep 10; done; \
    python -c "import fastapi, uvicorn"
COPY main.py .
ENV DB_PATH=/data/pact.db
VOLUME /data
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
