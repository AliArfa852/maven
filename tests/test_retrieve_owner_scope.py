"""The convenience retrieve() helpers pass the owner through to vector search.

They had no owner parameter, so any future caller would have searched every
user's documents. No caller used them yet; this keeps it that way safely.
"""

from src.personal_docs import retrieve_personal


class _FakeRag:
    def __init__(self):
        self.calls = []

    def search(self, query, k=5, owner=None):
        self.calls.append(owner)
        return [{"document": f"doc for {owner}", "metadata": {"source": "/x/a.txt"}}]


def test_retrieve_personal_passes_owner():
    rag = _FakeRag()
    out = retrieve_personal([], "q", 3, rag, owner="alice")
    assert rag.calls == ["alice"] and "doc for alice" in out[0]


def test_vector_retrieve_passes_owner():
    from src.rag_vector import VectorRAG

    seen = {}
    vr = VectorRAG.__new__(VectorRAG)
    vr.search = lambda q, k=5, owner=None: seen.setdefault("owner", owner) and [] or []
    vr.retrieve("q", 2, owner="bob")
    assert seen["owner"] == "bob"


def test_personal_docs_manager_retrieve_passes_owner():
    from src.personal_docs import PersonalDocsManager

    rag = _FakeRag()
    mgr = PersonalDocsManager.__new__(PersonalDocsManager)
    mgr.index, mgr.rag_manager = [], rag
    mgr.retrieve("q", owner="carol")
    assert rag.calls == ["carol"]
