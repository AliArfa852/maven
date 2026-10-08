"""Audit log v1: hash chain, what gets recorded, who may read it."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src import audit


@pytest.fixture
def audit_db(tmp_path, monkeypatch):
    """A private database so tampering with rows cannot affect other tests."""
    import core.database as database

    engine = create_engine(f"sqlite:///{tmp_path / 'audit.db'}")
    database.AuditEvent.__table__.create(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(database, "SessionLocal", factory)
    import routes.audit_routes as audit_routes
    monkeypatch.setattr(audit_routes, "SessionLocal", factory)
    yield factory
    engine.dispose()


def test_chain_verifies_and_links(audit_db):
    for i in range(5):
        assert audit.record("auth.login", actor=f"u{i}", target=f"u{i}", ip="10.0.0.1")
    out = audit.verify_chain(batch=2)  # several batches
    assert out["ok"] and out["count"] == 5 and len(out["head"]) == 64
    from core.database import AuditEvent
    db = audit_db()
    rows = db.query(AuditEvent).order_by(AuditEvent.id).all()
    assert rows[0].prev_hash == "" and all(b.prev_hash == a.hash for a, b in zip(rows, rows[1:]))
    db.close()


def test_changing_a_row_is_detected(audit_db):
    from core.database import AuditEvent
    for i in range(4):
        audit.record("access.roles", actor="admin", target=f"u{i}", detail={"after": ["basic"]})
    db = audit_db()
    row = db.query(AuditEvent).filter(AuditEvent.target == "u1").one()
    row.actor = "someone-else"
    row_id = row.id
    db.commit()
    db.close()
    out = audit.verify_chain()
    assert out == {"ok": False, "count": 1, "first_bad_id": row_id, "reason": "row changed after it was written"}


def test_removing_a_row_is_detected(audit_db):
    from core.database import AuditEvent
    for i in range(4):
        audit.record("auth.login", target=f"u{i}", outcome="failed")
    db = audit_db()
    db.query(AuditEvent).filter(AuditEvent.target == "u1").delete()
    db.commit()
    db.close()
    out = audit.verify_chain()
    assert not out["ok"] and "removed or changed" in out["reason"]


def test_record_never_raises(monkeypatch):
    import core.database as database

    def broken():
        raise RuntimeError("db down")

    monkeypatch.setattr(database, "SessionLocal", broken)
    assert audit.record("auth.login") is False


def test_long_values_are_clipped(audit_db):
    from core.database import AuditEvent
    audit.record("auth.login", target="x" * 5000, detail={"reason": "y" * 5000})
    db = audit_db()
    row = db.query(AuditEvent).one()
    assert len(row.target) == 300 and len(row.detail) <= 2000
    db.close()
    assert audit.verify_chain()["ok"]


@pytest.mark.parametrize("method, path, expected", [
    ("PUT", "/api/auth/users/bob/roles", True),
    ("POST", "/api/compliance/flags/1/decision", True),
    ("DELETE", "/api/tokens/abc", True),
    ("POST", "/api/import", True),
    ("GET", "/api/export", True),
    ("POST", "/api/auth/login", False),      # recorded by the route itself, with the username
    ("GET", "/api/auth/users", False),
    ("POST", "/api/chat_stream", False),
    ("POST", "/api/notes", False),
])
def test_what_the_middleware_records(method, path, expected):
    assert audit.should_audit(method, path) is expected


def _endpoint(path):
    from routes.audit_routes import setup_audit_routes
    for route in setup_audit_routes().routes:
        if route.path == path:
            return route.endpoint
    raise AssertionError(path)


def _request(user, caps):
    mgr = SimpleNamespace(is_configured=True, has_capability=lambda u, c: u == user and c in caps)
    return SimpleNamespace(headers={}, state=SimpleNamespace(current_user=user),
                           app=SimpleNamespace(state=SimpleNamespace(auth_manager=mgr)))


def test_basic_users_cannot_read_the_log(monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    for path in ("/api/audit/events", "/api/audit/verify"):
        with pytest.raises(HTTPException) as exc:
            _endpoint(path)(request=_request("bob", set()))
        assert exc.value.status_code == 403


@pytest.mark.parametrize("caps", [{"admin.view"}, {"compliance.review"}])
def test_viewers_and_compliance_read_the_log(audit_db, monkeypatch, caps):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    for i in range(3):
        audit.record("auth.login", actor="alice", target="alice")
    audit.record("auth.login", target="mallory", outcome="failed")
    req = _request("cora", caps)
    events = _endpoint("/api/audit/events")
    out = events(request=req, limit=2, before_id=None, actor=None, action=None, outcome=None)
    assert len(out["events"]) == 2 and out["next_before_id"]
    older = events(request=req, limit=100, before_id=out["next_before_id"], actor=None, action=None, outcome=None)
    assert len(older["events"]) == 2
    failed = events(request=req, limit=100, before_id=None, actor=None, action="auth.", outcome="failed")
    assert [e["target"] for e in failed["events"]] == ["mallory"]
    assert _endpoint("/api/audit/verify")(request=req)["ok"]
