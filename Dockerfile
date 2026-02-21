FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Install bambu-lab-cloud-api without deps (opencv-python is declared but unused at runtime).
# Then stub out opencv-python so pip's resolver considers it satisfied and won't try to
# build it from source (no C compiler, no armv7l wheel available).
RUN pip install --no-cache-dir bambu-lab-cloud-api --no-deps && \
    pip install --no-cache-dir paho-mqtt requests flask flask-cors flask-limiter && \
    python3 -c "import site, pathlib; \
        d = pathlib.Path(site.getsitepackages()[0]) / 'opencv_python-4.99.0.dist-info'; \
        d.mkdir(); \
        (d / 'METADATA').write_text('Metadata-Version: 2.1\nName: opencv-python\nVersion: 4.99.0\n'); \
        (d / 'INSTALLER').write_text('pip\n'); \
        (d / 'RECORD').write_text('')"

# Install project and remaining dependencies (pip sees opencv-python already satisfied)
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
