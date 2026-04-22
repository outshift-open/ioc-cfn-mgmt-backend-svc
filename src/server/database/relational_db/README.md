### Relational DB

PostgreSQL 17 Alpine is used as the Relational DB for this service.
https://hub.docker.com/_/postgres

#### Database Setup
```
docker compose -f docker/db.yaml up -d
```
Optionally - Set the below env variables in the `.env` file at the repo root (If using non-default values).
```
'POSTGRES_DB', 'cfn_mgmt'
'POSTGRES_USER', 'postgresUser'
'POSTGRES_PASSWORD', 'postgresPW'
'POSTGRES_HOST', 'localhost'
'POSTGRES_PORT', '5432'
```
- Use the correct env variables in the docker compose file.

#### Schema Migration

Database migration is performed using Atlas.
https://atlasgo.io/guides/orms/sqlalchemy/getting-started

To perform migration related tasks, run the following commands from the project root:

1. To apply an existing atlas migration
Migrations as indicated by the existing migration scripts will be applied to the database.
```
task db-migrate-apply
```

2. To generate a new atlas migration
If any new schema changes are added in relational_db/models, the below command will transform the models to .sql migration files in the migration folder.
```
task db-migrate-new -- "descriptive_msg_for_the_migration"
```

3. To get the migration status
```
task db-migrate-status
```

#### Data Population
1. Populate the software table entries via script using environment variables:
```bash
# Install postgresql client tools
brew install postgresql

# Using environment variables (recommended)
poetry run psql "postgresql://${POSTGRES_USER:-postgresUser}:${POSTGRES_PASSWORD:-postgresPW}@${POSTGRES_HOST:-localhost}:${POSTGRES_PORT:-5432}/${POSTGRES_DB:-cfn_mgmt}" -f scripts/populate_software.sql

# Or with explicit values
poetry run psql postgresql://postgresUser:postgresPW@localhost:5432/cfn_mgmt -f scripts/populate_software.sql
```
