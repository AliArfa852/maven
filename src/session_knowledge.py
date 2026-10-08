"""Search inside the current chat's files (plan v2 §4.2, Tier 1 knowledge).

Attachments are saved in full as Documents linked to the chat, but only the
first part of a long file fits in the message the model sees. This finds the
passages that answer a question across all of one chat's documents.

Scope is the chat itself: only Documents whose session_id is this chat and
whose owner is the asking user. Nothing from other chats or other users can
match, by construction of the query, not by filtering results afterwards.

Ranking is BM25 over overlapping chunks: no embedding model needed, works in
any language that separates words with spaces, and is predictable.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

CHUNK_CHARS = 1200
CHUNK_STEP = 1000           # 200 characters of overlap so a sentence at a boundary is not lost
MAX_DOCS = 50
MAX_TOTAL_CHARS = 3_000_000
MAX_RESULTS = 8
_WORD = re.compile(r"\w+", re.UNICODE)


@dataclass(frozen=True)
class Passage:
    document_id: str
    title: str
    offset: int
    text: str
    score: float


def _words(text: str) -> list[str]:
    return [w.lower() for w in _WORD.findall(text)]


def _chunks(text: str):
    """(offset, chunk) windows that end on whitespace where possible."""
    n, start = len(text), 0
    while start < n:
        end = min(n, start + CHUNK_CHARS)
        if end < n:
            cut = text.rfind(" ", start + CHUNK_STEP // 2, end)
            end = cut if cut > start else end
        yield start, text[start:end]
        if end >= n:
            break
        start = max(start + 1, end - (CHUNK_CHARS - CHUNK_STEP))


def _session_documents(session_id: str, owner: str | None):
    from core.database import Document, SessionLocal

    db = SessionLocal()
    try:
        q = db.query(Document.id, Document.title, Document.current_content).filter(
            Document.session_id == session_id,
            Document.archived.isnot(True),
        )
        q = q.filter(Document.owner.is_(None)) if owner is None else q.filter(Document.owner == owner)
        rows = q.order_by(Document.created_at.desc()).limit(MAX_DOCS).all()
    finally:
        db.close()
    out, total = [], 0
    for doc_id, title, content in rows:
        content = content or ""
        if total + len(content) > MAX_TOTAL_CHARS:
            content = content[: max(0, MAX_TOTAL_CHARS - total)]
        total += len(content)
        if content:
            out.append((doc_id, title or "Untitled", content))
        if total >= MAX_TOTAL_CHARS:
            break
    return out


def search(session_id: str, owner: str | None, query: str, k: int = 5) -> list[Passage]:
    """Best ``k`` passages for ``query`` in this chat's documents."""
    terms = list(dict.fromkeys(_words(query or "")))
    if not session_id or not terms:
        return []
    k = max(1, min(int(k or 5), MAX_RESULTS))

    chunks = []  # (doc_id, title, offset, text, term counts, length)
    for doc_id, title, content in _session_documents(session_id, owner):
        for offset, text in _chunks(content):
            words = _words(text)
            if words:
                chunks.append((doc_id, title, offset, text, Counter(words), len(words)))
    if not chunks:
        return []

    n = len(chunks)
    avg_len = sum(c[5] for c in chunks) / n
    df = {t: sum(1 for c in chunks if t in c[4]) for t in terms}
    k1, b = 1.5, 0.75
    scored = []
    for doc_id, title, offset, text, counts, length in chunks:
        score = 0.0
        for t in terms:
            tf = counts.get(t, 0)
            if not tf:
                continue
            idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
            score += idf * tf * (k1 + 1) / (tf + k1 * (1 - b + b * length / avg_len))
        if score > 0:
            scored.append(Passage(doc_id, title, offset, text.strip(), round(score, 3)))
    scored.sort(key=lambda p: (-p.score, p.offset))

    # One window per region: drop a passage that overlaps a better one in the same document.
    picked: list[Passage] = []
    for p in scored:
        if any(q.document_id == p.document_id and abs(q.offset - p.offset) < CHUNK_CHARS for q in picked):
            continue
        picked.append(p)
        if len(picked) >= k:
            break
    return picked


def format_results(passages: list[Passage], query: str) -> str:
    if not passages:
        return (f"No passage in this chat's files matches \"{query}\". Try other words, "
                "or list the chat's documents with manage_documents.")
    parts = [f"{len(passages)} passage(s) from this chat's files for \"{query}\":"]
    for i, p in enumerate(passages, 1):
        parts.append(f"\n[{i}] {p.title} (document {p.document_id}, from character {p.offset:,})\n{p.text}")
    parts.append("\nRead more around a passage with manage_documents action=read, document_id and offset.")
    return "\n".join(parts)
