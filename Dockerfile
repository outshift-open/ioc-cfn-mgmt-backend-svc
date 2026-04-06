# Build stage
FROM python:3.11-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create build user and workspace
RUN useradd -u 1001 app && mkdir /home/app
WORKDIR /home/app

# Use BuildKit cache mounts for pip and poetry
# This keeps the downloaded wheels and metadata between builds
ENV PIP_CACHE_DIR=/root/.cache/pip
ENV POETRY_CACHE_DIR=/root/.cache/pypoetry

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Upgrade pip and install poetry
RUN pip3 install --upgrade pip && pip3 install poetry

# Install dependencies
# Use CFLAGS to work around regopy ARM64 build issues
RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=cache,target=/root/.cache/pypoetry \
    && poetry config virtualenvs.create false \
    && CFLAGS="-Wno-error=array-bounds" poetry install --only=main --no-root

# Runtime stage
FROM python:3.11-slim AS runtime

# Link this container image to the GitHub repository
LABEL org.opencontainers.image.source=https://github.com/cisco-eti/ioc-cfn-mgmt-plane-svc

# Install only runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    postgresql-client \
    libatomic1 \
    && rm -rf /var/lib/apt/lists/*

# Create app user and directory
RUN useradd -u 1001 app \
    && mkdir /home/app \
    && chown -R app:app /home/app

WORKDIR /home/app

# Copy Python packages from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application source and scripts
COPY --chown=app:app src/ ./src/
COPY --chown=app:app scripts/ ./scripts/
COPY --chown=app:app pyproject.toml ./
COPY --chown=app:app docker-entrypoint.sh ./

# Make scripts executable
RUN chmod +x docker-entrypoint.sh scripts/migrate.sh

# Switch to app user
USER app

# Set environment variables
ENV PYTHONPATH="/home/app/src"

# Use entrypoint script to run initializations if required, then start server
ENTRYPOINT ["/home/app/docker-entrypoint.sh"]
