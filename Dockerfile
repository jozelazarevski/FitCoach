FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create persistent data directory
RUN mkdir -p /data
ENV FITCOACH_DB=/data/fitcoach.db

EXPOSE 5000

CMD python start.py && gunicorn app:app --bind 0.0.0.0:${PORT:-5000} --workers 2 --timeout 120
