"""Exchange CircleCI OIDC for a short-lived, write-only release session."""
"""Publish the tested Panoraiq image to Amazon ECR using CircleCI OIDC."""

import base64
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

import boto3


def validate_release(env, manifest, archive):
    if env.get("CIRCLE_BRANCH") != "main" or env.get("CIRCLE_PULL_REQUEST"):
        raise ValueError("Only an approved main-branch build can publish.")

    commit = env.get("CIRCLE_SHA1", "")
    if not re.fullmatch(r"[a-f0-9]{40}", commit):
        raise ValueError("Invalid release commit.")

    if manifest.get("commit") != commit:
        raise ValueError("Release commit does not match this pipeline.")

    with archive.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()

    if digest != manifest.get("archive_sha256"):
        raise ValueError("Release archive checksum mismatch.")

    for key in (
        "CIRCLE_OIDC_TOKEN_V2",
        "AWS_ROLE_ARN",
        "AWS_REGION",
        "ECR_REPOSITORY_URI",
    ):
        if not env.get(key):
            raise ValueError(f"Missing required release setting: {key}.")

    return commit


def run(*args, **kwargs):
    subprocess.run(args, check=True, **kwargs)


def publish():
    root = Path("artifacts")
    manifest = json.loads((root / "manifest.json").read_text())
    archive = root / "panoraiq-image.tar.gz"

    commit = validate_release(os.environ, manifest, archive)

    from botocore import UNSIGNED
    from botocore.config import Config

    sts = boto3.client(
        "sts",
        region_name=os.environ["AWS_REGION"],
        config=Config(signature_version=UNSIGNED),
    )

    credentials = sts.assume_role_with_web_identity(
        RoleArn=os.environ["AWS_ROLE_ARN"],
        RoleSessionName=f"panoraiq-{commit[:12]}",
        WebIdentityToken=os.environ["CIRCLE_OIDC_TOKEN_V2"],
        DurationSeconds=900,
    )["Credentials"]

    ecr = boto3.client(
        "ecr",
        region_name=os.environ["AWS_REGION"],
        aws_access_key_id=credentials["AccessKeyId"],
        aws_secret_access_key=credentials["SecretAccessKey"],
        aws_session_token=credentials["SessionToken"],
    )

    repository_uri = os.environ["ECR_REPOSITORY_URI"]
    repository_name = repository_uri.rsplit("/", 1)[1]
    registry = repository_uri.split("/", 1)[0]

    # Restore the exact image that passed CI.
    run("docker", "load", "--input", str(archive))

    local_image = f"panoraiq:{commit}"
    remote_image = f"{repository_uri}:{commit}"

    run("docker", "tag", local_image, remote_image)

    auth = ecr.get_authorization_token()["authorizationData"][0]
    username, password = base64.b64decode(
        auth["authorizationToken"]
    ).decode().split(":", 1)

    subprocess.run(
        ["docker", "login", "--username", username, "--password-stdin", registry],
        input=password,
        text=True,
        check=True,
    )

    run("docker", "push", remote_image)

    image = ecr.describe_images(
        repositoryName=repository_name,
        imageIds=[{"imageTag": commit}],
    )["imageDetails"][0]

    image_digest = image["imageDigest"]

    receipt = {
        "commit": commit,
        "image_tag": remote_image,
        "image_digest": image_digest,
        "image": f"{repository_uri}@{image_digest}",
        "archive_sha256": manifest["archive_sha256"],
    }

    (root / "release.json").write_text(
        json.dumps(receipt, indent=2) + "\n"
    )

    print(f"Published tested image: {repository_uri}@{image_digest}")


if __name__ == "__main__":
    publish()