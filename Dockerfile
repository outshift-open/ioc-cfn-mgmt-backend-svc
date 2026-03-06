# Builder Stage
FROM ghcr.io/cisco-eti/sre-python-docker:v3.11.9-hardened-debian-12 AS builder

WORKDIR /build

# Install build dependencies (curl for atlas, build-essential and python3-dev for compiling Python packages)
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Install poetry and dependencies to a specific location
# This compiles packages like greenlet that need python3-dev
RUN pip3 install --no-cache-dir poetry && \
    poetry config virtualenvs.create false && \
    poetry install --only=main --no-root --compile

# Install Atlas binary
RUN mkdir -p /build/bin && \
    curl -sSf https://atlasgo.sh | sh -s -- --no-install -o /build/bin/atlasgo -y && \
    chmod +x /build/bin/atlasgo

# Runtime Stage
FROM ghcr.io/cisco-eti/sre-python-docker:v3.11.9-hardened-debian-12

# Link this container image to the GitHub repository
LABEL org.opencontainers.image.source=https://github.com/cisco-eti/ioc-cfn-mgmt-plane-svc

# Install only runtime dependencies
# postgresql-client for database seeding
# libatomic1 is required for regopy on some architectures
RUN apt-get update && apt-get install -y \
    postgresql-client \
    libatomic1 \
    && rm -rf /var/lib/apt/lists/*

# Add user app
RUN useradd -u 1001 app

# Create the app directory and set permissions to app
RUN mkdir /home/app/ && chown -R app:app /home/app

WORKDIR /home/app

# Copy installed Python packages from builder 
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy Atlas binary from builder
COPY --from=builder --chown=app:app /build/bin/atlasgo /home/app/bin/atlasgo

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

# Use entrypoint script to run migrations then start server
ENTRYPOINT ["/home/app/docker-entrypoint.sh"]
