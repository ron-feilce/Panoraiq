"""Exchange CircleCI OIDC for a short-lived, write-only release session."""

import hashlib
import json
import os
import re
from pathlib import Path

import boto3


def validate_release(env, manifest, archive):
    if env.get("CIRCLE_BRANCH") != "main" or env.get("CIRCLE_PULL_REQUEST"):
        raise ValueError("Only an approved main-branch build can publish.")
    commit = env.get("CIRCLE_SHA1", "")
    if not re.fullmatch(r"[a-f0-9]{40}", commit) or manifest.get("commit") != commit:
        raise ValueError("Release commit does not match this pipeline.")
    with archive.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != manifest.get("archive_sha256"):
        raise ValueError("Release archive checksum mismatch.")
    for key in ("CIRCLE_OIDC_TOKEN_V2", "AWS_ROLE_ARN", "AWS_REGION", "ARTIFACT_BUCKET"):
        if not env.get(key):
            raise ValueError(f"Missing required release setting: {key}.")
    return commit


def publish():
    root = Path("artifacts")
    manifest = json.loads((root / "manifest.json").read_text())
    archive = root / "studio-image.tar.gz"
    commit = validate_release(os.environ, manifest, archive)
    # No static AWS keys are read; STS itself needs no prior credentials.
    from botocore import UNSIGNED
    from botocore.config import Config

    sts = boto3.client(
        "sts", region_name=os.environ["AWS_REGION"], config=Config(signature_version=UNSIGNED)
    )
    credentials = sts.assume_role_with_web_identity(
        RoleArn=os.environ["AWS_ROLE_ARN"],
        RoleSessionName=f"studio-{commit[:12]}",
        WebIdentityToken=os.environ["CIRCLE_OIDC_TOKEN_V2"],
        DurationSeconds=900,
    )["Credentials"]
    s3 = boto3.client(
        "s3",
        region_name=os.environ["AWS_REGION"],
        aws_access_key_id=credentials["AccessKeyId"],
        aws_secret_access_key=credentials["SecretAccessKey"],
        aws_session_token=credentials["SessionToken"],
    )
    bucket = os.environ["ARTIFACT_BUCKET"]
    prefix = f"releases/{commit}"
    for name in ("studio-image.tar.gz", "manifest.json"):
        s3.upload_file(
            str(root / name),
            bucket,
            f"{prefix}/{name}",
            ExtraArgs={"ServerSideEncryption": "AES256"},
        )
    receipt = {
        "commit": commit,
        "artifact": f"s3://{bucket}/{prefix}/studio-image.tar.gz",
        "archive_sha256": manifest["archive_sha256"],
    }
    (root / "release.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(f"Published tested image to s3://{bucket}/{prefix}/")


if __name__ == "__main__":
    publish()
