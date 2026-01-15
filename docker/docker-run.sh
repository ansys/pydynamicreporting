#!/bin/bash

IMAGE_NAME=pydynamicreporting-local

docker run -it --rm -v "$(pwd):/app" pydynamicreporting-local python