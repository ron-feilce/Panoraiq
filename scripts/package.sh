#!/usr/bin/env bash
set -euo pipefail
: "${IMAGE_TAG:?Set IMAGE_TAG to the tested commit SHA}"
mkdir -p artifacts
docker save "studio-ledger:$IMAGE_TAG" | gzip > artifacts/studio-image.tar.gz
docker image inspect "studio-ledger:$IMAGE_TAG" --format '{{.Id}}' > artifacts/image-id.txt
python3 scripts/release_manifest.py
