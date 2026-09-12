import hashlib

import pytest

from scripts.publish import validate_release


@pytest.fixture
def release(tmp_path):
    archive = tmp_path / "image.tar.gz"
    archive.write_bytes(b"test archive")
    commit = "a" * 40
    env = {
        "CIRCLE_BRANCH": "main",
        "CIRCLE_SHA1": commit,
        "CIRCLE_OIDC_TOKEN_V2": "test-token",
        "AWS_ROLE_ARN": "test-role",
        "AWS_REGION": "us-east-1",
        "ARTIFACT_BUCKET": "test-bucket",
    }
    manifest = {
        "commit": commit,
        "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
    }
    return env, manifest, archive


def test_matching_main_release_is_valid(release):
    assert validate_release(*release) == "a" * 40


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("CIRCLE_BRANCH", "feature/art"),
        ("CIRCLE_BRANCH", ""),
        ("CIRCLE_PULL_REQUEST", "https://github.com/owner/repo/pull/1"),
        ("CIRCLE_SHA1", "b" * 40),
        ("CIRCLE_SHA1", "../invalid"),
        ("CIRCLE_OIDC_TOKEN_V2", ""),
        ("AWS_ROLE_ARN", ""),
        ("ARTIFACT_BUCKET", ""),
    ],
)
def test_unapproved_or_mismatched_release_rejected(release, name, value):
    env, manifest, archive = release
    env[name] = value
    with pytest.raises(ValueError):
        validate_release(env, manifest, archive)


def test_tampered_archive_rejected(release):
    env, manifest, archive = release
    archive.write_bytes(b"changed")
    with pytest.raises(ValueError, match="checksum"):
        validate_release(env, manifest, archive)
