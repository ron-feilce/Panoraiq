import os
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

import click
from flask import Flask, abort, flash, redirect, render_template, request, url_for
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import event, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine import URL
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from panoraiq.models import MEDIA, STATUSES, DigitalEdition, Submission, Work, db


@event.listens_for(Engine, "connect")
def enable_sqlite_foreign_keys(connection, _):
    # Local fallback must enforce the same relationships as PostgreSQL.
    if connection.__class__.__module__.startswith("sqlite3"):
        connection.execute("PRAGMA foreign_keys=ON")


def field(name, limit, required=True):
    value = request.form.get(name, "").strip()
    if (required and not value) or len(value) > limit:
        raise ValueError(
            f"{name.replace('_', ' ').capitalize()} is required and must be "
            f"at most {limit} characters."
            if required
            else f"{name.replace('_', ' ').capitalize()} must be at most {limit} characters."
        )
    return value


def link(name, metadata=False):
    value = field(name, 2048, required=False)
    if not value:
        return value
    try:
        parsed = urlsplit(value)
        allowed = ("https", "http", "ipfs", "ar") if metadata else ("https", "http")
        valid = parsed.scheme in allowed and parsed.netloc and not parsed.username
        if not valid or any(char.isspace() for char in value):
            raise ValueError
    except ValueError:
        raise ValueError(
            f"{name.replace('_', ' ').capitalize()} must be a valid "
            f"{'HTTP(S), IPFS, or Arweave' if metadata else 'HTTP(S)'} link."
        ) from None
    return value


def chosen(name, choices):
    value = field(name, 20)
    if value not in choices:
        raise ValueError(f"Choose a valid {name}: {', '.join(choices)}.")
    return value


def form_date(name):
    try:
        return date.fromisoformat(field(name, 10))
    except ValueError:
        raise ValueError(f"{name.replace('_', ' ').capitalize()} must be a valid date.") from None


def database_url():
    if os.environ.get("DATABASE_URL"):
        return os.environ["DATABASE_URL"]

    if os.environ.get("DB_HOST"):
        return URL.create(
            drivername="postgresql+psycopg",
            username=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
            host=os.environ["DB_HOST"],
            port=int(os.environ.get("DB_PORT", "5432")),
            database=os.environ.get("DB_NAME", "panoraiq"),
        )

    return "sqlite:///panoraiq.db"


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY"),
        SQLALCHEMY_DATABASE_URI=database_url(),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        MAX_CONTENT_LENGTH=32 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE") == "true",
    )
    if test_config:
        app.config.update(test_config)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    if not app.config["SECRET_KEY"]:
        raise RuntimeError("Set SECRET_KEY to a random value before starting panoraiq Ledger.")
    db.init_app(app)
    CSRFProtect(app)

    @app.after_request
    def security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' https: http:; style-src 'self'; "
            "script-src 'self'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
        )
        return response

    def catalog(error=None, code=200):
        medium = request.args.get("medium", "")
        status = request.args.get("status", "")
        query = request.args.get("q", "").strip()
        if (medium and medium not in MEDIA) or (status and status not in STATUSES):
            abort(400, "Invalid filter.")
        all_works = db.session.scalars(
            select(Work).order_by(Work.created_on.desc(), Work.title)
        ).all()
        works = [
            work
            for work in all_works
            if (not medium or work.medium == medium)
            and (not status or work.status == status)
            and (not query or query.casefold() in f"{work.title} {work.description}".casefold())
        ]
        selected = None
        if request.args.get("work"):
            selected = db.get_or_404(Work, request.args["work"])
        counts = {state: sum(work.status == state for work in all_works) for state in STATUSES}
        return render_template(
            "index.html",
            works=works,
            all_works=all_works,
            selected=selected,
            medium=medium,
            status=status,
            query=query,
            counts=counts,
            media=MEDIA,
            statuses=STATUSES,
            today=date.today().isoformat(),
            error=error,
            values=request.form,
        ), code

    @app.get("/")
    def index():
        return catalog()

    @app.get("/healthz")
    def health():
        try:
            db.session.execute(text("SELECT 1"))
        except SQLAlchemyError:
            db.session.rollback()
            return {"status": "unavailable"}, 503
        return {"status": "ok"}

    @app.post("/works")
    def add_work():
        try:
            work = Work(
                title=field("title", 160),
                medium=chosen("medium", MEDIA),
                description=field("description", 5000, False),
                media_url=link("media_url"),
                created_on=form_date("created_on"),
                author=field("author", 160, False),
                copyright_note=field("copyright_note", 500, False),
            )
            db.session.add(work)
            db.session.commit()
        except ValueError as exc:
            return catalog(str(exc), 400)
        flash("Work added to your panoraiq.")
        return redirect(url_for("index", work=work.id), code=303)

    @app.post("/works/<work_id>/submissions")
    def add_submission(work_id):
        work = db.get_or_404(Work, work_id)
        try:
            submission = Submission(
                work=work,
                venue=field("venue", 160),
                submitted_on=form_date("submitted_on"),
                status=chosen("status", STATUSES),
            )
            db.session.add(submission)
            db.session.commit()
        except ValueError as exc:
            return catalog(str(exc), 400)
        flash("Submission recorded.")
        return redirect(url_for("index", work=work.id), code=303)

    @app.post("/submissions/<int:submission_id>/status")
    def update_submission(submission_id):
        submission = db.get_or_404(Submission, submission_id)
        try:
            submission.status = chosen("status", STATUSES)
            db.session.commit()
        except ValueError as exc:
            return catalog(str(exc), 400)
        flash("Submission status updated.")
        return redirect(url_for("index", work=submission.work_id), code=303)

    @app.post("/works/<work_id>/editions")
    def add_edition(work_id):
        work = db.get_or_404(Work, work_id)
        try:
            chain = field("chain", 80).lower()
            address = field("contract_address", 200)
            if address.startswith("0x"):
                address = address.lower()
            edition = DigitalEdition(
                work=work,
                chain=chain,
                contract_address=address,
                token_id=field("token_id", 160),
                metadata_uri=link("metadata_uri", metadata=True),
                transaction_hash=field("transaction_hash", 200, False),
                recorded_owner=field("recorded_owner", 200, False),
            )
            db.session.add(edition)
            db.session.commit()
        except ValueError as exc:
            return catalog(str(exc), 400)
        except IntegrityError:
            db.session.rollback()
            return catalog("That chain, contract, and token are already recorded.", 409)
        flash("Digital edition recorded. Ownership has not been verified.")
        return redirect(url_for("index", work=work.id), code=303)

    @app.cli.command("init-db")
    def init_db():
        """Create the initial schema; never drops existing records."""
        db.create_all()
        click.echo("panoraiq schema ready.")

    @app.cli.command("seed-demo")
    def seed_demo():
        """Add clearly fictional examples to an empty catalog only."""
        from panoraiq.seed import seed

        seed()
        click.echo("Demo catalog ready.")

    return app
