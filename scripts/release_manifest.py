"""Describe the release without copying environment variables or credentials."""

import hashlib
import json
import os
from pathlib import Path


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


if __name__ == "__main__":
    root = Path("artifacts")
    manifest = {
        "commit": os.environ["IMAGE_TAG"],
        "image": f"panoraiq:{os.environ['IMAGE_TAG']}",
        "image_id": (root / "panoraiq-image-id.txt").read_text().strip(),
        "archive_sha256": sha256(root / "panoraiq-image.tar.gz"),
        "database": "PostgreSQL 16",
        "tests": "pytest + release image HTTP/DB smoke test",
    }
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
