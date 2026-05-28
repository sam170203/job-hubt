"""Verify models map to the schema in spec §6 and basic CRUD works."""
from datetime import datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from job_hunt.models import (
    Application,
    Base,
    Contact,
    Event,
    GmailMessage,
    Job,
    StagingRaw,
)


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_insert_and_read_job(session):
    job = Job(
        source="hn",
        external_id="abc123",
        company="Acme",
        title="ML Engineer",
        url="https://example.com/job/1",
        scraped_at=datetime(2026, 5, 26, 9, 0),
    )
    session.add(job)
    session.commit()

    rows = session.scalars(select(Job)).all()
    assert len(rows) == 1
    assert rows[0].status == "new"
    assert rows[0].company == "Acme"


def test_unique_source_external_id(session):
    ts = datetime.utcnow()
    j1 = Job(source="hn", external_id="x", company="A", title="t", url="u1", scraped_at=ts)
    j2 = Job(source="hn", external_id="x", company="B", title="t2", url="u2", scraped_at=ts)
    session.add_all([j1, j2])
    with pytest.raises(Exception):
        session.commit()


def test_application_event_relationship(session):
    job = Job(source="hn", external_id="y", company="C", title="t", url="u",
              scraped_at=datetime.utcnow())
    session.add(job)
    session.flush()

    app = Application(
        job_id=job.id,
        applied_at=datetime.utcnow(),
        resume_variant="ai-ml",
        channel="direct",
    )
    session.add(app)
    session.flush()

    ev = Event(application_id=app.id, kind="reply", happened_at=datetime.utcnow())
    session.add(ev)
    session.commit()

    fetched_app = session.get(Application, app.id)
    assert len(fetched_app.events) == 1
    assert fetched_app.events[0].kind == "reply"


def test_staging_raw_payload_roundtrip(session):
    row = StagingRaw(
        source="hn",
        external_id="post123",
        payload={"raw": "anything", "nested": [1, 2, 3]},
        scraped_at=datetime.utcnow(),
    )
    session.add(row)
    session.commit()

    fetched = session.scalars(select(StagingRaw)).one()
    assert fetched.payload == {"raw": "anything", "nested": [1, 2, 3]}
    assert fetched.promoted is False


def test_contact_and_gmail_message_exist(session):
    c = Contact(name="Founder X", company="Acme", x_handle="@x")
    gm = GmailMessage(msg_id="abc", from_addr="r@acme.com", subject="hi",
                      received_at=datetime.utcnow(), parsed_signal="noise")
    session.add_all([c, gm])
    session.commit()
    assert session.scalars(select(Contact)).one().name == "Founder X"
    assert session.scalars(select(GmailMessage)).one().msg_id == "abc"


def test_init_db_creates_file(tmp_data_dir):
    from job_hunt import db

    db.reset_engine_for_testing()
    db.init_db()
    assert (tmp_data_dir / "jobs.db").exists()


def test_session_scope_commits(tmp_data_dir):
    from job_hunt import db
    from job_hunt.models import Contact

    db.reset_engine_for_testing()
    db.init_db()
    with db.session_scope() as s:
        s.add(Contact(name="Test"))
    with db.session_scope() as s:
        names = [c.name for c in s.query(Contact).all()]
    assert "Test" in names
