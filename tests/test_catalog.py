import uuid
from datetime import date

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from panoraiq.models import DigitalEdition, Submission, Work, db


def add_work(client, form):
    response = client.post("/works", data=form)
    assert response.status_code == 303
    return db.session.scalar(select(Work))


def test_work_persists_and_keeps_independent_identity(client, work_form):
    work = add_work(client, work_form)
    work_id = work.id
    uuid.UUID(work_id)
    db.session.remove()
    saved = db.session.get(Work, work_id)
    assert saved.title == "Observer State"
    assert saved.created_on == date(2026, 8, 24)
    assert saved.author == "An artist"
    assert saved.copyright_note == "All rights reserved."
    assert saved.editions == []
    assert saved.status == "draft"
    assert b"Observer State" in client.get("/").data


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("title", " "),
        ("title", "x" * 161),
        ("medium", "sculpture"),
        ("created_on", "2026-02-30"),
        ("created_on", ""),
        ("media_url", "javascript:alert(1)"),
        ("media_url", "https://"),
        ("media_url", "https://example.com/bad link"),
        ("description", "x" * 5001),
    ],
)
def test_invalid_work_rejected(client, work_form, field, value):
    work_form[field] = value
    assert client.post("/works", data=work_form).status_code == 400
    assert db.session.scalar(select(func.count()).select_from(Work)) == 0


def test_submission_and_status_update(client, work_form):
    work = add_work(client, work_form)
    response = client.post(
        f"/works/{work.id}/submissions",
        data={"venue": "Autumn Open Call", "submitted_on": "2026-09-01", "status": "submitted"},
    )
    assert response.status_code == 303
    db.session.expire_all()
    assert work.status == "submitted"
    submission = work.submissions[0]
    assert submission.work.id == work.id
    assert (
        client.post(f"/submissions/{submission.id}/status", data={"status": "selected"}).status_code
        == 303
    )
    assert work.status == "selected"
    assert b"Autumn Open Call" in client.get(f"/?work={work.id}").data


def test_work_must_exist_for_submission_and_edition(client):
    work_id = str(uuid.uuid4())
    assert client.post(f"/works/{work_id}/submissions", data={}).status_code == 404
    assert client.post(f"/works/{work_id}/editions", data={}).status_code == 404


@pytest.mark.parametrize("model", [Submission, DigitalEdition])
def test_foreign_key_enforced_below_http_layer(app, model):
    values = {"venue": "Gallery", "submitted_on": date.today(), "status": "submitted"}
    if model is DigitalEdition:
        values = {"chain": "eip155:1", "contract_address": "0xabc", "token_id": "1"}
    db.session.add(model(work_id=str(uuid.uuid4()), **values))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_invalid_status_rejected_by_form_and_database(client, work_form):
    work = add_work(client, work_form)
    response = client.post(
        f"/works/{work.id}/submissions",
        data={"venue": "Gallery", "submitted_on": "2026-09-01", "status": "minted"},
    )
    assert response.status_code == 400
    db.session.add(
        Submission(work_id=work.id, venue="Gallery", submitted_on=date.today(), status="minted")
    )
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_filter_combines_medium_status_and_search(client, work_form):
    work = add_work(client, work_form)
    db.session.add(
        Submission(work=work, venue="Gallery", submitted_on=date.today(), status="selected")
    )
    db.session.add(Work(title="Untitled Painting", medium="painting", created_on=date.today()))
    db.session.commit()
    page = client.get("/?medium=poetry&status=selected&q=observer")
    assert b"Observer State" in page.data
    assert b"Untitled Painting" not in page.data
    assert b"No works match" in client.get("/?medium=music").data
    assert client.get("/?status=minted").status_code == 400


def test_selected_priority_and_reverting_to_draft(client, work_form):
    work = add_work(client, work_form)
    for status in ("draft", "selected", "submitted"):
        db.session.add(
            Submission(work=work, venue=status, submitted_on=date.today(), status=status)
        )
    db.session.commit()
    db.session.expire_all()
    assert work.status == "selected"
    for submission in work.submissions:
        submission.status = "draft"
    db.session.commit()
    assert work.status == "draft"


def test_editions_optional_multi_chain_and_do_not_transfer_copyright(client, work_form):
    work = add_work(client, work_form)
    values = {
        "chain": "eip155:1",
        "contract_address": "0xABC",
        "token_id": "42",
        "metadata_uri": "ipfs://example/metadata.json",
        "recorded_owner": "collector",
    }
    assert client.post(f"/works/{work.id}/editions", data=values).status_code == 303
    assert client.post(f"/works/{work.id}/editions", data=values).status_code == 409
    values["chain"] = "eip155:137"
    assert client.post(f"/works/{work.id}/editions", data=values).status_code == 303
    db.session.expire_all()
    assert len(work.editions) == 2
    assert work.author == "An artist"
    assert work.copyright_note == "All rights reserved."
    assert work.status == "draft"
    assert work.editions[0].contract_address == "0xabc"
    page = client.get(f"/?work={work.id}")
    assert b"Unverified record" in page.data
    assert b"collector" in page.data


def test_csrf_is_required_in_normal_app(app, work_form):
    app.config["WTF_CSRF_ENABLED"] = True
    client = app.test_client()
    assert client.post("/works", data=work_form).status_code == 400
    import re

    page = client.get("/").data.decode()
    work_form["csrf_token"] = re.search(r'name="csrf_token" value="([^"]+)"', page)[1]
    assert client.post("/works", data=work_form).status_code == 303


def test_html_is_escaped_and_links_restricted(client, work_form):
    work_form["title"] = "<script>alert(1)</script>"
    add_work(client, work_form)
    page = client.get("/")
    assert b"<script>alert(1)</script>" not in page.data
    assert b"&lt;script&gt;" in page.data
    assert "frame-ancestors 'none'" in page.headers["Content-Security-Policy"]


def test_seed_is_explicit_and_idempotent(app, client):
    assert b"Make room for your first work" in client.get("/").data
    runner = app.test_cli_runner()
    assert runner.invoke(args=["init-db"]).exit_code == 0
    assert runner.invoke(args=["seed-demo"]).exit_code == 0
    assert runner.invoke(args=["seed-demo"]).exit_code == 0
    assert db.session.scalar(select(func.count()).select_from(Work)) == 6
    assert (
        db.session.scalar(select(Work).where(Work.title == "Observer State")).status == "selected"
    )


def test_health_and_missing_detail(client):
    assert client.get("/healthz").json == {"status": "ok"}
    assert client.get("/?work=missing").status_code == 404
