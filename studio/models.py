"""Works retain their identity independently of submissions or blockchain records."""

import uuid
from datetime import date

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import CheckConstraint, UniqueConstraint

db = SQLAlchemy()
MEDIA = ("painting", "poetry", "music")
STATUSES = ("draft", "submitted", "selected")


class Work(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = db.Column(db.String(160), nullable=False)
    medium = db.Column(db.String(20), nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    media_url = db.Column(db.String(2048), nullable=False, default="")
    created_on = db.Column(db.Date, nullable=False, default=date.today)
    author = db.Column(db.String(160), nullable=False, default="")
    copyright_note = db.Column(db.String(500), nullable=False, default="")
    submissions = db.relationship("Submission", backref="work", lazy="selectin",
                                  order_by="desc(Submission.submitted_on)")
    editions = db.relationship("DigitalEdition", backref="work", lazy="selectin")
    __table_args__ = (CheckConstraint("medium IN ('painting', 'poetry', 'music')",
                                     name="valid_work_medium"),)

    @property
    def status(self):
        states = {item.status for item in self.submissions}
        return next((state for state in reversed(STATUSES) if state in states), "draft")


class Submission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    work_id = db.Column(db.String(36), db.ForeignKey("work.id", ondelete="RESTRICT"),
                        nullable=False, index=True)
    venue = db.Column(db.String(160), nullable=False)
    submitted_on = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="submitted")
    __table_args__ = (CheckConstraint("status IN ('draft', 'submitted', 'selected')",
                                     name="valid_submission_status"),)


class DigitalEdition(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    work_id = db.Column(db.String(36), db.ForeignKey("work.id", ondelete="RESTRICT"),
                        nullable=False, index=True)
    chain = db.Column(db.String(80), nullable=False)
    contract_address = db.Column(db.String(200), nullable=False)
    token_id = db.Column(db.String(160), nullable=False)
    metadata_uri = db.Column(db.String(2048), nullable=False, default="")
    transaction_hash = db.Column(db.String(200), nullable=False, default="")
    # A manually recorded claim, not verified ownership or authorship.
    recorded_owner = db.Column(db.String(200), nullable=False, default="")
    __table_args__ = (UniqueConstraint("chain", "contract_address", "token_id",
                                     name="unique_chain_token"),)
