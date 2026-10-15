# Sandbox execution runner.
#
# Must be deployed to a host with a working Docker daemon (e.g. a Hetzner CX22
# VPS). PaaS containers cannot nest a daemon, which is why this is separate
# from the Flask API.
FROM python:3.11-slim

WORKDIR /srv

# The runner reuses the API's analyzer, so the repo (minus the frontend) is
# copied in. analyzer/ is the only Python package it needs.
COPY analyzer/ ./analyzer/
COPY runner/ ./runner/
COPY requirements.txt ./


RUN pip install --no-cache-dir -r requirements.txt gunicorn

# The API host calls this over a private interface; no ports are published.
# EXECUTION_RUNNER_SECRET must be supplied at run time or the app refuses to start.
ENV PYTHONUNBUFFERED=1 \
    EXECUTION_RUNNER_SECRET="" \
    RUN_BIND=127.0.0.1

EXPOSE 5001

# The pinned sandbox images are NOT pulled here: `docker build` cannot reach a
# daemon. Run scripts/prepull-images.sh on the host before starting the runner.

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:5001/healthz')"

# 4 workers is safe: each request is an independent container.
# Factory form so the secret check runs in the worker, not at import.
CMD ["sh", "-c", "exec gunicorn --bind ${RUN_BIND}:${RUN_PORT:-5001} --workers 4 --timeout 60 runner.server:create_runner_app()"]
