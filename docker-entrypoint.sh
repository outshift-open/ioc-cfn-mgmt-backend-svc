#!/bin/bash
set -e

echo "Starting application initialization..."

# Run database migrations
echo "Running database migrations..."
cd /home/app/src/server/database/relational_db
/home/app/bin/atlasgo migrate apply --dir "file://migrations" --env local
cd /home/app

# Seed the database with KEP adapters if the script exists
if [ -f "/home/app/src/server/database/relational_db/scripts/populate_software.sql" ]; then
    echo "Seeding database with KEP adapters..."
    cd /home/app/src/server/database/relational_db
    psql postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB} -f scripts/populate_software.sql
    cd /home/app
else
    echo "Warning: populate_software.sql not found, skipping database seeding"
fi

# Start the application
echo "Starting application server..."
exec uvicorn server.main:app --host 0.0.0.0 --port 9000
