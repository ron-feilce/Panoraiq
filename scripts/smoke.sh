#!/usr/bin/env bash
set -euo pipefail
docker compose -f compose.ci.yml run --rm app flask --app panoraiq init-db
docker compose -f compose.ci.yml up -d --wait --wait-timeout 90 app
docker compose -f compose.ci.yml run --rm smoke
