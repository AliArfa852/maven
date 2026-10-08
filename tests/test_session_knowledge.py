"""search_chat_files: passages from one chat's own documents only."""

import asyncio
import json
import uuid

import pytest

from src import session_knowledge


@pytest.fixture
def chat_docs(tmp_path, monkeypatch):
    """A private database: the shared in-memory one is reset by other tests."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import core.database as database
    from core.database import Base, Document, Session

    engine = create_engine(f"sqlite:///{tmp_path / 'chat.db'}")
    Base.metadata.create_all(engine, tables=[Session.__table__, Document.__table__])
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(database, "SessionLocal", factory)

    tag = uuid.uuid4().hex[:8]
    sid, other_sid = f"s-{tag}", f"o-{tag}"
    filler = " ".join(f"clause{i} general terms apply here." for i in range(600))
    contract = (filler + " The termination notice period is ninety days in writing. " + filler)
    db = factory()
    db.add_all([Session(id=sid, name="c", owner="alice", endpoint_url="x", model="m"),
                Session(id=other_sid, name="o", owner="alice", endpoint_url="x", model="m")])
    db.flush()
    db.add_all([
        Document(id=f"d1-{tag}", session_id=sid, owner="alice", title="Contract.pdf", current_content=contract),
        Document(id=f"d2-{tag}", session_id=sid, owner="alice", title="Notes", current_content="Lunch menu and parking."),
        # Same words, but another chat and another user: must never match.
        Document(id=f"d3-{tag}", session_id=other_sid, owner="alice", title="Other chat", current_content="termination notice period"),
        Document(id=f"d4-{tag}", session_id=sid, owner="mallory", title="Planted", current_content="termination notice period"),
        Document(id=f"d5-{tag}", session_id=sid, owner="alice", title="Archived", archived=True, current_content="termination notice"),
    ])
    db.commit()
    db.close()
    yield sid, tag
    engine.dispose()


def test_finds_the_passage_deep_inside_a_long_document(chat_docs):
    sid, tag = chat_docs
    hits = session_knowledge.search(sid, "alice", "termination notice period", k=5)
    assert hits and hits[0].document_id == f"d1-{tag}"
    assert "ninety days" in hits[0].text
    assert hits[0].offset > 20_000  # far past what fits inline


def test_scope_is_this_chat_and_this_user_only(chat_docs):
    sid, tag = chat_docs
    ids = {p.document_id for p in session_knowledge.search(sid, "alice", "termination notice period", k=8)}
    assert ids == {f"d1-{tag}"}
    assert {p.document_id for p in session_knowledge.search(sid, "mallory", "termination", k=8)} == {f"d4-{tag}"}
    assert session_knowledge.search(sid, "bob", "termination") == []


def test_no_overlapping_duplicates_and_k_is_capped(chat_docs):
    sid, _ = chat_docs
    hits = session_knowledge.search(sid, "alice", "general terms apply", k=50)
    assert len(hits) == session_knowledge.MAX_RESULTS
    by_doc = sorted(p.offset for p in hits)
    assert all(b - a >= session_knowledge.CHUNK_CHARS for a, b in zip(by_doc, by_doc[1:]))


def test_empty_or_unknown_queries():
    assert session_knowledge.search("", "alice", "x") == []
    assert session_knowledge.search("nope", "alice", "   ") == []
    assert "No passage" in session_knowledge.format_results([], "x")


def test_chunks_cover_the_whole_text_with_overlap():
    text = ("word " * 2000).strip()
    chunks = list(session_knowledge._chunks(text))
    assert chunks[0][0] == 0
    assert chunks[-1][0] + len(chunks[-1][1]) == len(text)
    assert all(b[0] < a[0] + len(a[1]) for a, b in zip(chunks, chunks[1:]))  # overlapping


def test_agent_tool(chat_docs):
    from src.agent_tools import TOOL_HANDLERS

    sid, tag = chat_docs
    run = TOOL_HANDLERS["search_chat_files"]
    out = asyncio.run(run(json.dumps({"query": "notice period"}), {"session_id": sid, "owner": "alice"}))
    assert out["exit_code"] == 0 and f"d1-{tag}" in out["response"] and "ninety days" in out["response"]
    assert asyncio.run(run(json.dumps({"query": "x"}), {"owner": "alice"}))["exit_code"] == 1
    assert asyncio.run(run(json.dumps({"query": ""}), {"session_id": sid}))["exit_code"] == 1


def test_tool_is_read_only_and_untrusted():
    from src.tool_capabilities import ResultIntegrity, ToolEffect, capabilities_for_action
    from src.tool_security import NON_ADMIN_BLOCKED_TOOLS, PLAN_MODE_READONLY_TOOLS

    caps = capabilities_for_action("search_chat_files", "{}")
    assert caps.effects == {ToolEffect.READ_SESSION}
    assert caps.result_integrity is ResultIntegrity.EXTERNAL_UNTRUSTED  # file text can carry injections
    assert "search_chat_files" in PLAN_MODE_READONLY_TOOLS
    assert "search_chat_files" not in NON_ADMIN_BLOCKED_TOOLS  # every user can search their own chat


def test_manage_documents_schema_offers_read_with_offset():
    from src.tool_schemas import FUNCTION_TOOL_SCHEMAS

    (schema,) = [s for s in FUNCTION_TOOL_SCHEMAS if s["function"]["name"] == "manage_documents"]
    props = schema["function"]["parameters"]["properties"]
    assert "read" in props["action"]["enum"] and "offset" in props


def test_earlier_attachments_keep_the_tool_in_reach(chat_docs):
    from src import agent_loop

    sid, _ = chat_docs
    assert agent_loop._session_has_documents(sid, "alice") is True
    assert agent_loop._session_has_documents(sid, "bob") is False
