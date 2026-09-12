# Connect the challenge pipeline

The source configuration is ready. Creating a public repository, connecting CircleCI,
applying branch/context restrictions, and provisioning a cloud destination are separate
account operations. Do not mark the challenge complete until a real run provides the
test report and cloud release receipt. The cloud target can be adapted if using an
existing service instead of the included AWS S3 path.

## 1. Repository and branch controls

Use `https://github.com/ron-feilce/Panoraiq`, with **main** as the default branch.
Confirm visibility is public. Connect this repository in CircleCI and select
`.circleci/config.yml`. Record the CircleCI **organization UUID** and **project UUID**.

In GitHub, protect `main` with a ruleset:

- Require a pull request, review approval, and the CircleCI `build-test` status check.
- Block direct pushes, force pushes, and branch deletion, including administrator bypass.
- Require review for changes to `.circleci/`, `scripts/`, and `infra/`.

These controls give "only on merge" its meaning. A branch filter alone also accepts
direct pushes. The initial bootstrap commit may need an explicitly managed exception
before protection is enabled. Future changes should be pull requests.

## 2. Prepare the AWS release destination

The reference target is **private S3 artifact storage**, not public app hosting.
The release contains a tested Docker image archive and integrity manifest. Use the
existing cloud target instead if required by your demonstration.

To prepare a new S3 target, render a CloudFormation template locally, replacing the
values below. This command does not create resources:

```sh
python infra/render.py --org-id YOUR-CIRCLECI-ORG-UUID --project-id YOUR-PROJECT-UUID --bucket YOUR-GLOBALLY-UNIQUE-BUCKET
```

Review `infra/generated/stack.json`. It defines a private encrypted, versioned bucket,
an HTTPS-only bucket policy, a CircleCI OIDC provider, and a role limited to writing
under `releases/`. If this AWS account already has the CircleCI organization’s OIDC
provider, add `--existing-provider-arn arn:aws:iam::ACCOUNT:oidc-provider/oidc.circleci.com/org/ORG-UUID`.
Use an existing bucket only after adapting the template/policy; this generator creates
a new bucket and does not import one.

Using an authorized AWS administrator session, provision the reviewed template:

```sh
aws cloudformation deploy --template-file infra/generated/stack.json --stack-name panoraiq-releases --capabilities CAPABILITY_IAM --region us-east-1
aws cloudformation describe-stacks --stack-name panoraiq-releases --region us-east-1 --query 'Stacks[0].Outputs'
```

Store the output bucket name and role ARN for the next step. Standard storage/request
charges apply. The bucket is retained when the stack is deleted, including old versions;
remove it deliberately when the demonstration is over if no longer needed.

The IAM trust checks audience plus the V2 subject’s exact organization, project,
`github.com/ron-feilce/Panoraiq` origin, and `refs/heads/main`. Only the user ID is a
wildcard. Feature branches and fork origins cannot assume the role even if their code
changes the job’s branch environment variable. This follows
[CircleCI’s OIDC branch restrictions](https://circleci.com/docs/guides/permissions-authentication/openid-connect-tokens/).

## 3. Restrict the CircleCI release context

Create **panoraiq-production** with project access restricted to this project and a
security group restricted to release approvers. Set these non-secret identifiers:

| Variable | Value |
| --- | --- |
| `AWS_ROLE_ARN` | CloudFormation `PublisherRoleArn` |
| `AWS_REGION` | Bucket’s AWS region |
| `ARTIFACT_BUCKET` | CloudFormation `ArtifactBucket` |

Do not add AWS access keys to project variables or a context. Leave **Pass secrets to
builds from forked pull requests** disabled. Add this context expression restriction:

```text
pipeline.git.branch == "main" and not job.ssh.enabled and not (pipeline.config_source starts-with "api")
```

This uses [CircleCI’s documented context restrictions](https://circleci.com/docs/guides/security/contexts/).
If context security groups are unavailable for your account integration, configure the
equivalent supported restrictions before enabling publication. The release job obtains
AWS credentials only after `approve-release`, stores them in process memory, and requests
a 900-second session. Tests and Docker builds have no AWS context or AWS credentials.

IAM validates branch/repository/project identity; it does **not** verify CircleCI’s
approval graph. Required reviews of trusted `main` configuration and CircleCI’s approval
and context controls enforce that part of the boundary. Context IDs are not assumed to
be supported IAM claim keys. See the [AWS OIDC condition-key reference](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_iam-condition-keys.html).

## 4. Demonstrate the complete run

1. Open a PR with an app change: custom image builds and tests run beside PostgreSQL;
   JUnit appears in CircleCI’s Tests tab. No publication job runs on the feature branch.
2. Intentionally make a test fail on a temporary branch: observe that publication is
   blocked and test reports/logs remain available. Restore the test before merging.
3. Merge the reviewed PR: `main` builds and tests, then waits for an authorized approver.
4. Approve the release. `publish` checks the commit and archive checksum before STS
   exchanges the V2 OIDC token. It uploads `releases/COMMIT/panoraiq-image.tar.gz` and
   `manifest.json`. A `release-receipt.json` artifact records the S3 location and hash.
5. Open a docs-only PR: the change script halts expensive jobs. A docs-only `main`
   workflow may still show its approval node; the downstream publish job also halts
   without exchanging the OIDC token or uploading anything.

The comparison is first parent on `main` (covering an entire merged change) or the
merge base with `origin/main` on feature branches. Missing history runs full checks.
Failed tests stop packaging; only successful image bundles enter the workspace.

## 5. Retrieve and run a release

Use your own authorized read session (the CI publishing role deliberately cannot read
the bucket). Replace `BUCKET` and `COMMIT` below:

```sh
aws s3 cp s3://BUCKET/releases/COMMIT/panoraiq-image.tar.gz panoraiq-image.tar.gz
aws s3 cp s3://BUCKET/releases/COMMIT/manifest.json manifest.json
python -c "import hashlib,json; expected=json.load(open('manifest.json'))['archive_sha256']; actual=hashlib.file_digest(open('panoraiq-image.tar.gz','rb'),'sha256').hexdigest(); assert actual == expected; print('Checksum verified')"
docker load --input panoraiq-image.tar.gz
docker image inspect panoraiq-ledger:COMMIT --format '{{.Id}}'
```

Compare the image ID with `manifest.json`, then run it with a persistent PostgreSQL
`DATABASE_URL` and a fresh `SECRET_KEY`. Initialize its database with `flask --app panoraiq
init-db` using the same image. Local Compose shows the runtime wiring. A public runtime
also needs authenticated HTTPS access; the catalog is intentionally a single-user app.
