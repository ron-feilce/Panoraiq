import os

import pytest
from sqlalchemy.engine import make_url

from panoraiq import create_app
from panoraiq.models import db


@pytest.fixture
def app():
    url = os.environ.get("TEST_DATABASE_URL", "sqlite:///:memory:")
    parsed = make_url(url)
    if os.environ.get("REQUIRE_POSTGRES") == "true" and parsed.get_backend_name() != "postgresql":
        pytest.fail("CI requires PostgreSQL; SQLite cannot substitute for integration tests.")
    if parsed.get_backend_name() == "postgresql" and not (parsed.database or "").endswith("_test"):
        pytest.fail("Tests recreate tables: use a disposable database whose name ends in _test.")
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-only-secret",
            "SQLALCHEMY_DATABASE_URI": url,
            "WTF_CSRF_ENABLED": False,
        }
    )
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def work_form():
    return {
        "title": "Observer State",
        "medium": "poetry",
        "description": "A quiet observation.",
        "created_on": "2026-08-24",
        "media_url": "https://example.com/poem",
        "author": "An artist",
        "copyright_note": "All rights reserved.",
    }
