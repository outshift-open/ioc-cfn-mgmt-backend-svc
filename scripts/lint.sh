#!/bin/bash -e
set -e

CHECK_ONLY=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --check)
      CHECK_ONLY=true
      shift
      ;;
    *)
      shift
      ;;
  esac
done

echo "Checking for formatting issues with Black..."
if [ "$CHECK_ONLY" = true ]; then
  poetry run black --check src/
else
  poetry run black src/
fi

echo ""
echo "Running Flake8 linter..."
poetry run flake8 src/ --max-line-length=120

echo ""
echo "Linting DONE"
