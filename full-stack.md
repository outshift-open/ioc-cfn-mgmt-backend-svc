# IOC - Full Stack
Run the full stack (UI + Backend + DB) using docker-compose.

## Prerequisites
Authenticate github to access and pull Docker images from GitHub Container Registry (GHCR) where IOC images are hosted.

Authorise cisco-eti docker hub account to pull images:
- go to https://github.com/settings/tokens
- If you don't have a token yet, create a new one with `read:packages` scope
- If you already have a token, ensure it has `read:packages` scope
- Click on "Configure SSO" beside delete button
- Authorize the token for cisco-eti organization
- Use the token to login to Docker Hub:
```bash
export GITHUB_TOKEN="xxxxxxxxxxxxx"  # replace with your token
echo "$GITHUB_TOKEN" | docker login ghcr.io -u "YOUR_GITHUB_USERNAME" --password-stdin
```

## Steps
- Uses `env.conf` file for environment variables. You can modify as needed.

- Start services (pulls latest images)
```bash
task docker-compose-full-stack-up
```

- Stop services
```bash
task docker-compose-full-stack-down
```

Volumes are preserved when stopping services. To remove volumes, use:
```bash
task docker-compose-full-stack-down-with-volumes
```

## Service Endpoints

Once all services are running, access them at:

- **IOC Management UI**: http://localhost:9001 (username and password are defined in env.conf)
- **IOC Management API**: http://localhost:9000/docs
- **CFN Service**: http://localhost:9002
- **Knowledge Memory Service**: http://localhost:9003
- **AgensGraph Database**: localhost:5456
- **AgensGraph Viewer**: http://localhost:5457

### Future Services (Currently Commented Out)

The following services are defined in docker-compose.yml but commented out pending image availability:

- **Cognitive Agent - Knowledge Management**: Port 9004 (when enabled)
- **Cognitive Agent - Semantic Negotiation**: Port 9005 (when enabled)

To enable these services, uncomment their definitions in docker-compose.yml.
