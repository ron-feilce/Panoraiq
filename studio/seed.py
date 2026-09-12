from datetime import date

from sqlalchemy import select

from studio.models import Submission, Work, db


def seed():
    if db.session.scalar(select(Work.id).limit(1)):
        return
    examples = [
        (
            "Observer State",
            "poetry",
            "A poem about the quiet space between witnessing and being seen.",
            "2026-08-24",
        ),
        (
            "A Place to Return",
            "painting",
            "Warm earth, a distant horizon. A study in remembering home.",
            "2026-08-18",
        ),
        (
            "Blue Hours",
            "music",
            "An ambient sketch for piano, tape, and the last light of the day.",
            "2026-08-10",
        ),
        (
            "The Shape of Silence",
            "painting",
            "Overlapping forms, leaving room for what is unsaid.",
            "2026-07-28",
        ),
        (
            "Notes from the Window",
            "poetry",
            "Small observations collected over a long summer.",
            "2026-07-14",
        ),
        (
            "Still, Growing",
            "painting",
            "A little green finding its way through an ordinary afternoon.",
            "2026-06-30",
        ),
    ]
    for title, medium, description, created in examples:
        work = Work(
            title=title,
            medium=medium,
            description=description,
            created_on=date.fromisoformat(created),
            author="Demo artist",
            copyright_note="Fictional demonstration record. All rights reserved.",
        )
        db.session.add(work)
        if title in ("Observer State", "Blue Hours"):
            db.session.add(
                Submission(
                    work=work,
                    venue="Sample: Autumn Open Call",
                    submitted_on=date(2026, 9, 1),
                    status="selected" if medium == "poetry" else "submitted",
                )
            )
    db.session.commit()
