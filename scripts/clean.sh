#!/usr/bin/env bash
set -euo pipefail

echo "Cleaning __pycache__ and *.pyc..."
find . -type d -name __pycache__ -prune -exec rm -rf {} +
find . -type f -name "*.pyc" -delete
echo "Done."

