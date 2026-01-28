FROM --platform=linux/arm64 ghcr.io/cisco-eti/sre-python-docker:v3.11.9-hardened-debian-12

# OCI image labels for package metadata and repository linking
LABEL org.opencontainers.image.source="https://github.com/cisco-eti/ioc-cfn-mgmt-backend"
LABEL org.opencontainers.image.description="IOC CFN Management Backend - FastAPI service for TKF platform workspace and resource management"
LABEL org.opencontainers.image.licenses="Proprietary"

# Install curl for health checks, wget for atlas installation, postgresql-client for database seeding, and build essentials for regopy
RUN apt-get update && apt-get install -y curl wget postgresql-client build-essential libatomic1 && rm -rf /var/lib/apt/lists/*

# Add user app
RUN useradd -u 1001 app

# Create the app directory and set permissions to app
RUN mkdir /home/app/ && chown -R app:app /home/app

WORKDIR /home/app

COPY --chown=app:app pyproject.toml poetry.lock ./

# Install poetry and dependencies as root to avoid permission issues
RUN pip3 install poetry
RUN poetry config virtualenvs.create false
RUN poetry install --only=main --no-root

# Install Atlas binary for migrations
RUN mkdir -p /home/app/bin && \
    curl -sSf https://atlasgo.sh | sh -s -- --no-install -o /home/app/bin/atlasgo -y && \
    chmod +x /home/app/bin/atlasgo && \
    chown -R app:app /home/app/bin

# Copy application source and scripts
COPY --chown=app:app src/ ./src/
COPY --chown=app:app scripts/ ./scripts/
COPY --chown=app:app docker-entrypoint.sh ./

# Make entrypoint executable
RUN chmod +x docker-entrypoint.sh

# run the application as user app
USER app

ENV PYTHONPATH="/home/app/src"
ENV PATH="/home/app/bin:/home/app/.local/bin:$PATH"

# Use entrypoint script to run migrations, generate DEK, then start server
ENTRYPOINT ["/home/app/docker-entrypoint.sh"]
