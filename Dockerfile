FROM python:3.11-slim

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

# Build frontend (only needed if serving from Flask)
COPY package.json package-lock.json ./
RUN npm ci --production
COPY index.html vite.config.js ./
COPY src/ src/
RUN npx vite build

# Expose the port (Railway/Render set PORT env var)
EXPOSE 5000

# Use Gunicorn for production (not Flask dev server)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "30", "app:app"]
