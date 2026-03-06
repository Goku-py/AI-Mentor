FROM python:3.11-slim

# Suppress interactive prompts during apt-get install
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies for code execution (subprocess)
RUN apt-get update && apt-get install -y --no-install-recommends \
    nodejs \
    npm \
    gcc \
    g++ \
    default-jdk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir gunicorn

# Copy application code
COPY app.py analyzer.py ./

# Build frontend
COPY package.json package-lock.json ./
RUN npm ci
COPY index.html vite.config.js ./
COPY src/ src/
RUN npx vite build
# Remove devDependencies after build to keep image lean
RUN npm prune --omit=dev

# Expose a default port
EXPOSE 5000

# Use Gunicorn for production (not Flask dev server)
# The shell form of CMD allows evaluating the $PORT environment variable
CMD gunicorn --bind 0.0.0.0:${PORT:-5000} --workers 2 --timeout 30 app:app
