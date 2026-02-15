FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir ".[standalone]"

# Copy application code
COPY . .

# Create data directory for SQLite
RUN mkdir -p /app/data

# Collect static files
ENV DJANGO_SETTINGS_MODULE=standalone.settings
RUN python standalone/manage.py collectstatic --noinput 2>/dev/null || true

# Supervisor config to run both web and collector
COPY docker/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

EXPOSE 8000

CMD ["supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
