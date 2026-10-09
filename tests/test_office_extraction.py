"""Uploaded Word / Excel / PowerPoint files are readable without markitdown.

Before, .xlsx and .pptx were dropped and .docx lost its tables whenever the
optional markitdown package was missing (the default install).
"""
import pytest

from src import markitdown_runtime as m
from src.file_builder import build_file

DOC = {"title": "Q3", "blocks": [
    {"type": "heading", "text": "Summary"},
    {"type": "paragraph", "text": "Revenue up"},
    {"type": "bullets", "items": ["North +20%"]},
    {"type": "table", "rows": [["Region", "Rev"], ["North", 120]]},
]}


@pytest.fixture(autouse=True)
def no_markitdown(monkeypatch):
    def missing():
        raise RuntimeError(m.MARKITDOWN_MISSING)
    monkeypatch.setattr(m, "load_markitdown", missing)


def _write(tmp_path, fmt, spec):
    path = tmp_path / f"f.{fmt}"
    path.write_bytes(build_file(fmt, spec).data)
    return str(path)


def test_xlsx_sheets_become_markdown_tables(tmp_path):
    text = m.convert_to_markdown(_write(tmp_path, "xlsx", {"sheets": [
        {"name": "Sales", "rows": [["Region", "Rev"], ["North", 120], ["a|b", None]]},
        {"name": "Empty", "rows": []},
    ]}))
    assert "## Sheet: Sales" in text and "| North | 120 |" in text
    assert "a\\|b" in text            # pipes escaped so the table stays intact
    assert "Empty" not in text        # empty sheets skipped


def test_xlsx_row_cap(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "NATIVE_MAX_ROWS_PER_SHEET", 5)
    text = m.convert_to_markdown(_write(tmp_path, "xlsx", {"rows": [[i] for i in range(50)]}))
    assert "first 5 rows shown" in text and "| 49 |" not in text


def test_pptx_titles_text_tables_notes_without_repeating_titles(tmp_path):
    text = m.convert_to_markdown(_write(tmp_path, "pptx", {"slides": [
        {"title": "Goals", "bullets": ["Ship v1"], "notes": "say hi"},
        {"title": "Budget", "table": [["Item", "Cost"], ["GPU", 5000]]},
    ]}))
    assert "## Slide 1: Goals" in text and "- Ship v1" in text and "Notes: say hi" in text
    assert "| GPU | 5000 |" in text
    assert "- Goals" not in text


def test_docx_keeps_headings_lists_and_tables(tmp_path):
    text = m.convert_to_markdown(_write(tmp_path, "docx", DOC))
    assert "# Summary" in text and "- North +20%" in text and "| North | 120 |" in text


def test_unreadable_file_returns_none(tmp_path):
    bad = tmp_path / "broken.xlsx"
    bad.write_bytes(b"not a zip")
    assert m.convert_to_markdown(str(bad)) is None
