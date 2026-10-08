"""analyze_data: exact figures from the user's own spreadsheet."""

import asyncio
import json
from datetime import datetime

import pytest

from src import data_analysis as da


@pytest.mark.parametrize("raw, num", [
    (12, 12.0), (3.5, 3.5), ("1,234.50", 1234.5), ("1.234,50", 1234.5), ("$1,200", 1200.0),
    ("(500)", -500.0), ("-42", -42.0), ("12%", 0.12), ("€ 99", 99.0), ("3,5", 3.5),
    ("1,234,567", 1234567.0), ("USD 10", 10.0),
    ("", None), (None, None), ("abc", None), (True, None), ("12 apples", None),
])
def test_number_parsing(raw, num):
    assert da.to_number(raw) == num


def _sales_xlsx(path):
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Sales"
    ws.append(["Date", "Region", "Revenue", "Status"])
    data = [
        (datetime(2026, 1, 5), "North", 120, "Paid"), (datetime(2026, 1, 20), "South", 80, "Paid"),
        (datetime(2026, 2, 3), "North", "1,000", "Open"), (datetime(2026, 4, 9), "East", 95.5, "Paid"),
        (datetime(2026, 4, 30), "South", "(20)", "Refund"), (None, "North", None, "Open"),
    ]
    for row in data:
        ws.append(list(row))
    wb.create_sheet("Notes").append(["just text"])
    wb.save(path)


@pytest.fixture
def sales(tmp_path):
    p = tmp_path / "sales.xlsx"
    _sales_xlsx(p)
    return da.load_table(str(p), "sales.xlsx")


def test_load_xlsx(sales):
    assert sales.columns == ["Date", "Region", "Revenue", "Status"]
    assert sales.sheet == "Sales" and sales.sheets == ["Sales", "Notes"]
    assert len(sales.rows) == 6


def test_describe(sales):
    out = da.run(sales, {"operation": "describe"})
    cols = {c["column"]: c for c in out["columns"]}
    assert cols["Revenue"]["type"] == "number" and cols["Revenue"]["sum"] == 1275.5
    assert cols["Revenue"]["empty"] == 1
    assert cols["Date"]["type"] == "date" and cols["Date"]["first"] == "2026-01-05"
    assert cols["Region"]["most_common"][0] == ("North", 3)


def test_group_by_region_sorted_by_total(sales):
    out = da.run(sales, {"operation": "group", "group_by": ["Region"],
                         "aggregates": [{"column": "Revenue", "fn": "sum"}, {"fn": "count"}]})
    assert out["columns"] == ["Region", "sum of Revenue", "count"]
    assert out["rows"] == [["North", 1120, 3], ["East", 95.5, 1], ["South", 60, 2]]


def test_group_by_month_and_quarter_in_time_order(sales):
    month = da.run(sales, {"operation": "group", "group_by": ["Date:month"],
                           "aggregates": [{"column": "Revenue", "fn": "sum"}]})
    assert [r[0] for r in month["rows"]] == ["2026-01", "2026-02", "2026-04", None]  # blanks last
    q = da.run(sales, {"operation": "group", "group_by": ["date:quarter"],
                       "aggregates": [{"column": "revenue", "fn": "avg"}]})
    assert ["2026-Q1", 400] in q["rows"]


def test_filters_then_aggregate(sales):
    out = da.run(sales, {"operation": "group", "group_by": ["Status"],
                         "where": [{"column": "Revenue", "op": ">", "value": 90}],
                         "aggregates": [{"column": "Revenue", "fn": "sum"}]})
    assert out["rows_after_filter"] == 3
    assert dict((r[0], r[1]) for r in out["rows"]) == {"Open": 1000, "Paid": 215.5}
    dated = da.run(sales, {"operation": "rows", "where": {"column": "Date", "op": ">=", "value": "2026-04-01"},
                           "columns": ["Region"]})
    assert dated["rows"] == [["East"], ["South"]]
    text = da.run(sales, {"operation": "rows", "where": [{"column": "Status", "op": "contains", "value": "ref"}]})
    assert len(text["rows"]) == 1


def test_top(sales):
    out = da.run(sales, {"operation": "top", "sort_by": "Revenue", "limit": 2, "columns": ["Region", "Revenue"]})
    assert out["rows"] == [["North", "1,000"], ["North", 120]]
    low = da.run(sales, {"operation": "top", "sort_by": "Revenue", "descending": False, "limit": 1})
    assert low["rows"][0][1] == "South"


@pytest.mark.parametrize("req, msg", [
    ({"operation": "explode"}, "operation must be"),
    ({"operation": "group", "group_by": ["Nope"]}, "No column named"),
    ({"operation": "group", "group_by": ["Region"], "aggregates": [{"column": "Revenue", "fn": "variance"}]}, "fn must be"),
    ({"operation": "group", "group_by": ["Date:week"]}, "bucket"),
    ({"operation": "rows", "where": [{"column": "Region", "op": "~"}]}, "op must be"),
])
def test_bad_requests_explain_themselves(sales, req, msg):
    with pytest.raises(da.AnalysisError, match=msg):
        da.run(sales, req)


def test_csv_with_semicolons_and_header_row(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("Report generated today\nName;Amount\nA;1.234,50\nB;10\n", encoding="utf-8")
    t = da.load_table(str(p), "x.csv", header_row=2)
    assert t.columns == ["Name", "Amount"]
    out = da.run(t, {"operation": "describe"})
    assert out["columns"][1]["sum"] == 1244.5


def test_unknown_sheet_and_type(tmp_path, sales):
    p = tmp_path / "sales.xlsx"
    _sales_xlsx(p)
    with pytest.raises(da.AnalysisError, match="No sheet named"):
        da.load_table(str(p), "sales.xlsx", sheet="Budget")
    with pytest.raises(da.AnalysisError, match="Only Excel"):
        da.load_table(str(p), "sales.pdf")


def test_markdown_output(sales):
    md = da.to_markdown(da.run(sales, {"operation": "group", "group_by": ["Region"],
                                       "aggregates": [{"column": "Revenue", "fn": "sum"}]}))
    assert "| Region | sum of Revenue |" in md and "| North | 1120 |" in md
    assert "Revenue | number" in da.to_markdown(da.run(sales, {"operation": "describe"}))


# ── the agent tool ──────────────────────────────────────────────────────────

class _Uploads:
    def __init__(self, path, owner):
        self.path, self.owner, self.calls = path, owner, []

    def resolve_upload(self, upload_id, owner=None, allow_admin=True):
        self.calls.append(allow_admin)
        if upload_id == "abc.xlsx" and owner == self.owner:
            return {"id": upload_id, "path": self.path, "name": "sales.xlsx"}
        return None


def _run_tool(monkeypatch, handler, args, ctx, attached=(("abc.xlsx", "sales.xlsx"),)):
    import src.agent_tools.file_tools as file_tools
    import src.tool_utils as tool_utils
    from src.agent_tools import TOOL_HANDLERS

    monkeypatch.setattr(tool_utils, "get_upload_handler", lambda: handler)
    monkeypatch.setattr(file_tools, "chat_upload_ids", lambda sid, owner: list(attached))
    ctx = {"session_id": "s1", **ctx}
    return asyncio.run(TOOL_HANDLERS["analyze_data"](json.dumps(args), ctx))


def test_tool_reads_only_the_callers_upload(tmp_path, monkeypatch):
    p = tmp_path / "abc.xlsx"
    _sales_xlsx(p)
    h = _Uploads(str(p), "alice")
    ok = _run_tool(monkeypatch, h, {"file_id": "abc.xlsx", "operation": "group", "group_by": ["Region"],
                                    "aggregates": [{"column": "Revenue", "fn": "sum"}]}, {"owner": "alice"})
    assert ok["exit_code"] == 0 and "| North | 1120 |" in ok["response"]
    denied = _run_tool(monkeypatch, h, {"file_id": "abc.xlsx", "operation": "describe"}, {"owner": "mallory"})
    assert denied["exit_code"] == 1 and "that you can read" in denied["error"]
    assert h.calls == [False, False]  # never the admin override
    bad = _run_tool(monkeypatch, h, {"file_id": "abc.xlsx", "operation": "group", "group_by": ["x"]}, {"owner": "alice"})
    assert bad["exit_code"] == 1 and "No column named" in bad["error"]
    # No file_id: the newest spreadsheet attached to the chat.
    auto = _run_tool(monkeypatch, h, {"operation": "describe"}, {"owner": "alice"})
    assert auto["exit_code"] == 0
    none = _run_tool(monkeypatch, h, {"operation": "describe"}, {"owner": "alice"}, attached=[])
    assert none["exit_code"] == 1 and "No spreadsheet is attached" in none["error"]


def test_tool_refuses_files_not_attached_to_this_chat(tmp_path, monkeypatch):
    p = tmp_path / "abc.xlsx"
    _sales_xlsx(p)
    h = _Uploads(str(p), "alice")
    out = _run_tool(monkeypatch, h, {"file_id": "abc.xlsx", "operation": "describe"}, {"owner": "alice"},
                    attached=[("other.xlsx", "other.xlsx")])
    assert out["exit_code"] == 1 and "not attached to this chat" in out["error"]
    assert h.calls == []  # refused before the upload store was touched
    no_chat = asyncio.run(__import__("src.agent_tools", fromlist=["TOOL_HANDLERS"]).TOOL_HANDLERS["analyze_data"](
        json.dumps({"file_id": "abc.xlsx", "operation": "describe"}), {"owner": "alice"}))
    assert no_chat["exit_code"] == 1


def test_chat_reads_pass_the_external_context_gate_but_private_reads_do_not():
    from src.tool_capabilities import ToolRunSecurityContext

    gate = ToolRunSecurityContext(external_untrusted_context_seen=True)
    assert gate.decision_for("analyze_data", "{}").allowed
    assert gate.decision_for("search_chat_files", "{}").allowed
    assert not gate.decision_for("read_email", "{}").allowed
    assert not gate.decision_for("web_fetch", "{}").allowed


def test_latest_spreadsheet_in_the_chat(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import core.database as database
    from core.database import Base, ChatMessage, Session
    from src.agent_tools.file_tools import latest_table_upload

    engine = create_engine(f"sqlite:///{tmp_path / 'c.db'}")
    Base.metadata.create_all(engine, tables=[Session.__table__, ChatMessage.__table__])
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(database, "SessionLocal", factory)
    db = factory()
    db.add(Session(id="s1", name="n", owner="alice", endpoint_url="x", model="m"))
    db.flush()
    for i, atts in enumerate([[{"id": "old.xlsx", "name": "old.xlsx"}],
                              [{"id": "pic.png", "name": "pic.png"}, {"id": "new.csv", "name": "new.csv"}],
                              [{"id": "notes.pdf", "name": "notes.pdf"}]]):
        db.add(ChatMessage(id=f"m{i}", session_id="s1", role="user", content="x",
                           meta_data=json.dumps({"attachments": atts}),
                           timestamp=datetime(2026, 10, 1, 10, i)))
    db.commit()
    db.close()
    assert latest_table_upload("s1", "alice") == "new.csv"
    assert latest_table_upload("s1", "mallory") is None
    engine.dispose()


def test_tool_registration():
    from src.tool_capabilities import ResultIntegrity, ToolEffect, capabilities_for_action
    from src.tool_schemas import FUNCTION_TOOL_SCHEMAS
    from src.tool_security import NON_ADMIN_BLOCKED_TOOLS, PLAN_MODE_READONLY_TOOLS

    caps = capabilities_for_action("analyze_data", "{}")
    assert caps.effects == {ToolEffect.READ_SESSION}
    assert caps.result_integrity is ResultIntegrity.EXTERNAL_UNTRUSTED
    assert "analyze_data" in PLAN_MODE_READONLY_TOOLS and "analyze_data" not in NON_ADMIN_BLOCKED_TOOLS
    assert any(s["function"]["name"] == "analyze_data" for s in FUNCTION_TOOL_SCHEMAS)
