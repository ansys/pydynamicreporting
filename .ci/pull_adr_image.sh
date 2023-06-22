#!/bin/sh
set -ex

# Image name
_IMAGE_NAME="ghcr.io/ansys-internal/nexus_dev"

# Pull Ansys Dynamic Reporting image based on tag
docker pull $_IMAGE_NAME

# Remove all dangling images
docker image prune -f
