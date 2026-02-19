#!/bin/bash
set -e
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "CREATE DATABASE cfn_cp;"
echo "Database 'cfn_cp' created successfully"
