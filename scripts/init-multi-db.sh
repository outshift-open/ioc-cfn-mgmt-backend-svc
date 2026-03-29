#!/bin/bash
set -e

# Create additional databases needed by management and CFN services.
# This script runs inside the ioc-knowledge-db container on first init.
# TODO: Remove cfn_cp(audits not required for clawbee release) once the CFN Python service is hooked up here
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE cfn_mgmt;
    CREATE DATABASE cfn_cp;
EOSQL

echo "Databases 'cfn_mgmt' and 'cfn_cp' created successfully"
