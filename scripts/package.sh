#!/usr/bin/env bash
set -euo pipefail
: "${IMAGE_TAG:?Set IMAGE_TAG to the tested commit SHA}"
mkdir -p artifacts
docker save "panoraiq-ledger:$IMAGE_TAG" | gzip > artifacts/panoraiq-image.tar.gz
docker image inspect "panoraiq-ledger:$IMAGE_TAG" --format '{{.Id}}' > artifacts/image-id.txt
python3 scripts/release_manifest.py
