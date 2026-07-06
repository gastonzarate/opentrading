FROM python:3.12-slim AS base
# Build stage

# Set work directory
WORKDIR /app

COPY . /app

# Install build dependencies (if needed)
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
RUN pip install --no-cache-dir -r requirements/base.txt

# Create a non-root user
RUN groupadd -r deployer && useradd -r -m -g deployer deployer

# Set proper permissions
RUN chown -R deployer:deployer /app

# Switch to non-root user
USER deployer

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# EXPOSE port
EXPOSE 8000

FROM base AS prod

# collectstatic runs at build time and only needs settings to import. Provide
# build-time defaults for the settings that are otherwise required from the
# environment; the running container overrides these via its env_file.
ENV ENVIRONMENT=build \
    DEBUG=False

RUN python manage.py collectstatic --noinput  --clear
