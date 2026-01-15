#!/bin/bash

set -e

IMAGE_NAME=pydynamicreporting-local

cd "$(dirname "$0")/.."

echo "Building PyDynamicReporting docker image..."
docker build -t $IMAGE_NAME -f docker/Dockerfile .

echo ""
echo "Build complete."
echo "Run it with: ./docker-run.sh"