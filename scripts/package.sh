#!/usr/bin/env bash
set -euo pipefail
: "${IMAGE_TAG:?Set IMAGE_TAG to the tested commit SHA}"
mkdir -p artifacts
docker save "panoraiq:$IMAGE_TAG" | gzip > artifacts/panoraiq-image.tar.gz
docker image inspect "panoraiq:$IMAGE_TAG" --format '{{.Id}}' > artifacts/panoraiq-image-id.txt
python3 scripts/release_manifest.py
