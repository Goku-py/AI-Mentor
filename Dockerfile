FROM node:22-slim@sha256:7af03b14a13c8cdd38e45058fd957bf00a72bbe17feac43b1c15a689c029c732 AS frontend

WORKDIR /frontend

COPY package.json package-lock.json ./
RUN npm ci

COPY index.html vite.config.ts tsconfig.json public/ ./
COPY src/ src/
RUN npx vite build

FROM python:3.11-slim@sha256:a3ab0b966bc4e91546a033e22093cb840908979487a9fc0e6e38295747e49ac0

# Suppress interactive prompts during apt-get install
ENV DEBIAN_FRONTEND=noninteractive
ENV HOST_EXECUTION_ENABLED=1

# Install system dependencies for code execution (subprocess)
RUN apt-get update && apt-get install -y --no-install-recommends \
    nodejs \
    npm \
    gcc \
    g++ \
    default-jdk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies from pinned lockfile (reproducible builds)
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock

# Copy core files
COPY app.py analyzer.py ./
COPY app_pkg/ app_pkg/
COPY models_pkg/ models_pkg/
COPY migrations/ migrations/

COPY --from=frontend /frontend/dist dist

# Create a non-root user for security and own the app directory
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Expose a default port
EXPOSE 5000

# Basic container healthcheck
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/api/v1/health', timeout=2)"

# Use Gunicorn for production (not Flask dev server)
CMD ["sh","-c","exec gunicorn --bind 0.0.0.0:${PORT:-5000} --workers 2 --timeout 30 app:app"]
