#!/bin/bash
set -e

# Set variables here
REPO="adclab/fastjwt"
VERSION="v0.7"

# Build image with both tags
docker build \
  -t ${REPO}:${VERSION} \
  -t ${REPO}:latest \
  .

# Push both tags
docker push ${REPO}:${VERSION}
docker push ${REPO}:latest