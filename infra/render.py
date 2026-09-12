"""Render reviewable CloudFormation; does not contact or modify AWS."""

import argparse
import json
import re
import uuid
from pathlib import Path


def template(org, project, repository, bucket, existing_provider=None):
    org, project = str(uuid.UUID(org)), str(uuid.UUID(project))
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("Repository must be owner/name, without wildcards.")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,61}[a-z0-9]", bucket):
        raise ValueError(
            "Choose a globally unique bucket name: 3–63 lowercase letters/digits/hyphens."
        )
    issuer = f"oidc.circleci.com/org/{org}"
    resources = {
        "Artifacts": {
            "Type": "AWS::S3::Bucket",
            "DeletionPolicy": "Retain",
            "UpdateReplacePolicy": "Retain",
            "Properties": {
                "BucketName": bucket,
                "BucketEncryption": {
                    "ServerSideEncryptionConfiguration": [
                        {"ServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}
                    ]
                },
                "PublicAccessBlockConfiguration": {
                    "BlockPublicAcls": True,
                    "BlockPublicPolicy": True,
                    "IgnorePublicAcls": True,
                    "RestrictPublicBuckets": True,
                },
                "VersioningConfiguration": {"Status": "Enabled"},
                "LifecycleConfiguration": {
                    "Rules": [
                        {
                            "Id": "AbortIncompleteUploads",
                            "Status": "Enabled",
                            "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 1},
                        }
                    ]
                },
            },
        },
        "BucketPolicy": {
            "Type": "AWS::S3::BucketPolicy",
            "Properties": {
                "Bucket": {"Ref": "Artifacts"},
                "PolicyDocument": {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Deny",
                            "Principal": "*",
                            "Action": "s3:*",
                            "Resource": [f"arn:aws:s3:::{bucket}", f"arn:aws:s3:::{bucket}/*"],
                            "Condition": {"Bool": {"aws:SecureTransport": "false"}},
                        }
                    ],
                },
            },
        },
        "PublisherRole": {
            "Type": "AWS::IAM::Role",
            "Properties": {
                "MaxSessionDuration": 3600,
                "AssumeRolePolicyDocument": {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": {"Federated": existing_provider or {"Ref": "CircleOIDC"}},
                            "Action": "sts:AssumeRoleWithWebIdentity",
                            "Condition": {
                                "StringEquals": {f"{issuer}:aud": org},
                                "StringLike": {
                                f"{issuer}:sub": (
                                    f"org/{org}/project/{project}/user/*/vcs-origin/"
                                    f"github.com/{repository}/vcs-ref/refs/heads/main"
                                )
                                },
                            },
                        }
                    ],
                },
                "Policies": [
                    {
                        "PolicyName": "PublishTestedRelease",
                        "PolicyDocument": {
                            "Version": "2012-10-17",
                            "Statement": [
                                {
                                    "Effect": "Allow",
                                    "Action": ["s3:PutObject", "s3:AbortMultipartUpload"],
                                    "Resource": f"arn:aws:s3:::{bucket}/releases/*",
                                }
                            ],
                        },
                    }
                ],
            },
        },
    }
    if not existing_provider:
        resources["CircleOIDC"] = {
            "Type": "AWS::IAM::OIDCProvider",
            "Properties": {"Url": f"https://{issuer}", "ClientIdList": [org]},
        }
    return {
        "AWSTemplateFormatVersion": "2010-09-09",
        "Description": "Studio Ledger: private release artifacts and restricted CircleCI OIDC",
        "Resources": resources,
        "Outputs": {
            "ArtifactBucket": {"Value": {"Ref": "Artifacts"}},
            "PublisherRoleArn": {"Value": {"Fn::GetAtt": ["PublisherRole", "Arn"]}},
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--org-id", required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--repository", default="ron-feilce/Panoraiq")
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--existing-provider-arn")
    parser.add_argument("--output", default="infra/generated/stack.json")
    args = parser.parse_args()
    result = template(
        args.org_id, args.project_id, args.repository, args.bucket, args.existing_provider_arn
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {output}. Review it before deploying; no AWS resources were changed.")
