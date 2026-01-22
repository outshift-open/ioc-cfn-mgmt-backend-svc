#!/bin/bash
set -e

echo "Starting application initialization..."

# Generate DEK if config.json doesn't exist
if [ ! -f /home/app/src/server/config.json ]; then
    echo "Generating Data Encryption Key..."
    python3 /home/app/scripts/generate_DEK.py
else
    echo "DEK config already exists, skipping generation"
fi

# Run database migrations
echo "Running database migrations..."
cd /home/app/src/server/database/relational_db
atlasgo migrate apply --dir "file://migrations" --env local
cd /home/app

# Seed the database with KEP adapters
echo "Seeding database with KEP adapters..."
cd /home/app/src/server/database/relational_db
psql postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB} -f scripts/populate_software.sql
cd /home/app

# Start the application
echo "Starting application server..."
exec uvicorn server.main:app --host 0.0.0.0 --port 8000
