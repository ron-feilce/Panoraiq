import pytest

from infra.render import template

ORG = "11111111-1111-4111-8111-111111111111"
PROJECT = "22222222-2222-4222-8222-222222222222"


def test_trust_is_bound_to_org_project_repo_and_main():
    stack = template(ORG, PROJECT, "ron-feilce/Panoraiq", "panoraiq-test-artifacts")
    role = stack["Resources"]["PublisherRole"]["Properties"]
    condition = role["AssumeRolePolicyDocument"]["Statement"][0]["Condition"]
    assert condition["StringEquals"] == {f"oidc.circleci.com/org/{ORG}:aud": ORG}
    assert condition["StringLike"][f"oidc.circleci.com/org/{ORG}:sub"] == (
        f"org/{ORG}/project/{PROJECT}/user/*/vcs-origin/"
        "github.com/ron-feilce/Panoraiq/vcs-ref/refs/heads/main"
    )
    permissions = role["Policies"][0]["PolicyDocument"]["Statement"][0]
    assert permissions["Action"] == ["s3:PutObject", "s3:AbortMultipartUpload"]
    assert permissions["Resource"] == "arn:aws:s3:::panoraiq-test-artifacts/releases/*"
    bucket = stack["Resources"]["Artifacts"]
    assert all(bucket["Properties"]["PublicAccessBlockConfiguration"].values())
    assert bucket["DeletionPolicy"] == "Retain"


def test_wildcard_repository_is_rejected():
    with pytest.raises(ValueError):
        template(ORG, PROJECT, "ron-feilce/*", "panoraiq-test-artifacts")


def test_existing_provider_is_reused():
    arn = f"arn:aws:iam::123456789012:oidc-provider/oidc.circleci.com/org/{ORG}"
    stack = template(ORG, PROJECT, "ron-feilce/Panoraiq", "panoraiq-test-artifacts", arn)
    assert "CircleOIDC" not in stack["Resources"]
    role = stack["Resources"]["PublisherRole"]["Properties"]
    assert role["AssumeRolePolicyDocument"]["Statement"][0]["Principal"]["Federated"] == arn
