#!/bin/bash
# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0
set -e

# Create additional databases needed by management and CFN services.
# This script runs inside the ioc-knowledge-db container on first init.
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE cfn_mgmt;
EOSQL

echo "Database 'cfn_mgmt' created successfully"
