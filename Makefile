.PHONY: help deps install-update-poetry poetry-check generate-openapi-spec dev run test test-coverage lint-check lint clean
.PHONY: docker-build docker-run docker-compose-full-stack-up docker-compose-full-stack-up-build docker-compose-full-stack-down docker-compose-full-stack-down-with-volumes
.PHONY: docker-compose-db-up docker-compose-db-down docker-compose-db-down-with-volumes
.PHONY: db-migrate-apply db-migrate-status db-seed

# Load environment variables from env.conf if it exists
-include env.conf
export

# Variables
SRC_DIR := $(PWD)/src
PYTHON := python3
BIN_DIR := $(PWD)/bin
GIT_COMMIT_SHA := $(shell git rev-parse --short HEAD 2>/dev/null || echo "unknown")
GIT_COMMIT_TIME := $(shell git log -1 --format=%cI 2>/dev/null || echo "unknown")
GIT_BRANCH := $(shell git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
ENV_FILE := env.conf

# Default target
help: ## Show this help message
	@echo "Available targets:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## ' Makefile | sed 's/:.*## /|/' | sort | awk -F'|' '{printf "  \033[36mmake %-45s\033[0m %s\n", $$1, $$2}'
	@echo ""

## Dependency Management ##

deps: install-update-poetry poetry-check ## Install all dependencies (Python)

install-update-poetry: ## Install and update Python dependencies using Poetry
	poetry update

poetry-check: ## Validate poetry configuration
	poetry check

## Development ##

generate-openapi-spec: ## Generate OpenAPI specification and save to docs/openapi/openapi.json
	poetry run python scripts/generate_openapi_spec.py

dev: deps db-migrate-apply generate-openapi-spec ## Start development server with hot reload
	cd $(SRC_DIR) && poetry run uvicorn server.main:app --host 0.0.0.0 --port 9000 --reload

run: deps db-migrate-apply generate-openapi-spec ## Start production server (installs deps, applies db migrations, then runs)
	cd $(SRC_DIR) && poetry run python -m server.main

## Testing ##

test: ## Run all tests with pytest
	poetry run pytest tests/ -v

test-coverage: ## Run tests with coverage report
	poetry run pytest tests/ --cov=server --cov-report=term-missing

## Code Quality ##

lint-check: ## Run linting checks
	./scripts/lint.sh --check

lint: ## Fix linting issues automatically
	./scripts/lint.sh

clean: ## Clean Python cache files
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete

## Docker Tasks ##

docker-build: ## Build Docker image
	docker build -t $${IMAGE_NAME} -f Dockerfile .

docker-run: ## Run Docker container
	docker compose --env-file $(ENV_FILE) up ioc-cfn-mgmt-plane-svc

## Docker Compose - Full Stack ##

docker-compose-full-stack-up: ## Start all services with docker-compose
	docker compose --env-file $(ENV_FILE) --profile full-stack up --pull always -d
	docker compose --env-file $(ENV_FILE) --profile full-stack logs -f

docker-compose-full-stack-up-build: ## Start all services with docker-compose, rebuilding images
	docker compose --env-file $(ENV_FILE) --profile full-stack up --build --pull always -d
	docker compose --env-file $(ENV_FILE) --profile full-stack logs -f

docker-compose-full-stack-down: ## Stop all services with docker-compose
	docker compose --env-file $(ENV_FILE) --profile full-stack down

docker-compose-full-stack-down-with-volumes: ## Stop all services and remove volumes
	docker compose --env-file $(ENV_FILE) --profile full-stack down -v

## Docker Compose - Database Only ##

docker-compose-db-up: ## Start only databases (PostgreSQL) with db-only profile
	docker compose --env-file $(ENV_FILE) --profile db-only up -d --pull always

docker-compose-db-down: ## Stop only databases with db-only profile
	docker compose --env-file $(ENV_FILE) --profile db-only down

docker-compose-db-down-with-volumes: ## Stop databases and remove volumes
	docker compose --env-file $(ENV_FILE) --profile db-only down -v

## Database Migration ##

db-migrate-apply: ## Apply pending database migrations
	./scripts/migrate.sh apply

db-migrate-status: ## Show database migration status
	./scripts/migrate.sh status

db-seed: ## Seed the database with initial data
	cd $(SRC_DIR)/server/database/relational_db && poetry run psql postgresql://$$POSTGRES_USER:$$POSTGRES_PASSWORD@localhost:$$POSTGRES_PORT/cfn_mgmt -f scripts/populate_software.sql
