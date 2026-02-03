#!/bin/bash
set -e

echo "Running unit tests with pytest..."
poetry run pytest tests/ -v

echo "UNIT-TEST DONE"
