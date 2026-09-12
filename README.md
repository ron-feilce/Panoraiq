# panoraiq Ledger

A small artist’s panoraiq inventory, built for the CircleCI Field Engineer challenge.
Paintings, poems, music, and the places they go. Flask, PostgreSQL, and one page.

Repository: [ron-feilce/Panoraiq](https://github.com/ron-feilce/Panoraiq).

## Run with Docker and PostgreSQL

Requires Docker with Compose v2. In PowerShell:

```powershell
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"
```

Edit `.env`: set `SECRET_KEY` to the generated value and use another random hex value
for `POSTGRES_PASSWORD` (hex avoids URL-escaping issues). Then:

```sh
docker compose build
docker compose run --rm app flask --app panoraiq init-db
docker compose run --rm app flask --app panoraiq seed-demo
docker compose up -d
```

Open **http://localhost:8000**. `seed-demo` is optional and only inserts into an empty
catalog. Its six fictional examples include *Observer State*, selected for a sample
open call. Illustration placeholders are explicitly labeled; replace them with your
own media links. Nothing is uploaded or minted.

`docker compose down` stops the app and preserves PostgreSQL data. Do not add `--volumes`
unless you intend to delete the local catalog.

## Run without Docker (local SQLite preview)

Python 3.12+; the container uses Python 3.12. From PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
$env:SECRET_KEY = .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
.\.venv\Scripts\python.exe -m flask --app panoraiq init-db
.\.venv\Scripts\python.exe -m flask --app panoraiq seed-demo
.\.venv\Scripts\python.exe -m flask --app panoraiq run
```

Open **http://localhost:5000**. SQLite is a convenient preview and unit-test fallback;
the required CI integration tests explicitly refuse to run without PostgreSQL.
Set `DATABASE_URL=postgresql+psycopg://user:password@host:5432/panoraiq` to use PostgreSQL
outside Compose. Keep `SECRET_KEY` stable between app restarts if preserving sessions.

This is a single-user demonstration with no login. Compose binds only to loopback.
For public hosting, place it behind an authenticated HTTPS proxy, set
`COOKIE_SECURE=true`, and provision persistent PostgreSQL. The release destination
below stores an artifact; it does not host a live web application.

## What you can do

- Add a work with title, medium, description, creation date, and optional media link.
- Open its detail panel and record gallery/event submissions; update their statuses.
- Combine medium and status filters with a title/description search.
- Optionally record digital editions, including chain, contract, token, metadata URI,
  transaction hash, and an unverified recorded owner.

Work status is derived: **selected** if any submission is selected, otherwise
**submitted** if any is submitted, otherwise **draft**. A UUID identifies the work
independently of its editions. Foreign keys reject orphan records; database constraints
reject invalid statuses and duplicate chain/contract/token combinations. Use consistent
chain IDs such as `eip155:1`; identifiers are manual records, without chain verification.
Author and copyright information belong to the work, and token-owner claims belong to
editions. Recording or transferring a token does not update authorship or copyright.

`init-db` creates the initial schema without dropping data. It is not a migration
system; introduce versioned migrations before changing a populated production schema.

## Test

```powershell
.\.venv\Scripts\python.exe -m pytest --junitxml=test-results/junit.xml --cov=panoraiq
.\.venv\Scripts\python.exe -m ruff check panoraiq tests scripts infra
```

To exercise the same PostgreSQL container arrangement as CI, in Bash:

```sh
export IMAGE_TAG=local
docker build --target runtime -t panoraiq:local .
docker build --target test -t panoraiq-tests:local .
docker build --target smoke -t panoraiq-smoke:local .
mkdir -p test-results && chmod 777 test-results
docker compose -f compose.ci.yml run --rm tests
bash scripts/smoke.sh
docker compose -f compose.ci.yml down --volumes
```

Tests recreate their tables and accept only PostgreSQL database names ending in
`_test`. Always use a disposable test database. Local Compose and CI use separate
databases and volume arrangements.

## Challenge evidence

| Requirement | Implementation / evidence |
| --- | --- |
| Public VCS + CircleCI | Repository above; connect it using [the setup guide](docs/circleci-setup.md). A successful live run is still required. |
| Custom Docker image built and used in pipeline | `Dockerfile` runtime/test targets; tests run in the custom test image derived from runtime; HTTP/DB smoke test uses the exact runtime image that is packaged. |
| Collectable test results | `pytest --junitxml=/results/junit.xml`; CircleCI `store_test_results`, coverage XML and container logs as artifacts. |
| PostgreSQL secondary container | `compose.ci.yml` starts `postgres:16-bookworm` alongside the test/app containers on a CircleCI machine executor. |
| Conditional work | `ci-changes.sh` skips documentation-only changes; release depends on successful tests and approval, with a `main` branch filter. |
| Shell + non-scripting language | Bash orchestration, Python Flask, and a compiled Java HTTP/database smoke client (`tools/SmokeCheck.java`). |
| Artifact published to cloud | Tested Docker archive and SHA-256 manifest uploaded to a private Amazon S3 bucket (AWS cloud object storage). This is artifact publication, not an application hosting deployment. |
| Only on merge to default branch | `main` filter **plus required GitHub branch protection** against direct pushes; see setup guide. |
| Credentials restricted / OIDC | Approved release job, restricted CircleCI context, exact org/project/repo/main IAM trust; 15-minute AWS session, no static AWS keys. |

See [CircleCI setup](docs/circleci-setup.md) for required external controls and
[the demo walkthrough](docs/demo.md) for a short presentation.
