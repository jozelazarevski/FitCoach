# Stage 1: Install dependencies
FROM python:3.12-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Production image
FROM python:3.12-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code (exclude dev files via .dockerignore)
COPY . .

# Create persistent data directory
RUN mkdir -p /data

# Production environment
ENV FITCOACH_DB=/data/fitcoach.db \
    FITCOACH_ENV=production \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/health')" || exit 1

CMD python start.py && gunicorn app:app --bind 0.0.0.0:${PORT:-5000} --workers 2 --timeout 120
