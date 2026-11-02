#!/bin/sh
set -ex

# Image name
_IMAGE_NAME="ghcr.io/snps-ansys-internal/adr_dev:latest"

# Pull Ansys Dynamic Reporting image based on tag
docker pull $_IMAGE_NAME
