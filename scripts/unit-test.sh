#!/bin/bash
# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0
set -e

echo "Running unit tests with pytest..."
poetry run pytest tests/ -v

echo "UNIT-TEST DONE"
