"""Helpers for the optional markitdown document-extraction dependency.

markitdown (MIT, Microsoft) converts Office/EPUB documents to Markdown, which is
more token-efficient and model-legible than a raw text dump. It is **optional**:
install with `pip install -r requirements-optional.txt`. When absent, callers
degrade gracefully (chat shows a hint; the RAG indexer skips the file) — the MIT
core never hard-depends on it. Mirrors the optional-dependency pattern in
`src/pdf_runtime.py`.
"""

import logging
import os

logger = logging.getLogger(__name__)

MARKITDOWN_MISSING = (
    "Office/EPUB document extraction requires markitdown. Install optional "
    "dependencies with `pip install -r requirements-optional.txt`."
)

# Formats routed through markitdown. PDFs stay on pypdf (src/document_processor
# and src/personal_docs); plain text/code/csv/json/markdown/html stay on the
# cheaper built-in text path. These are the formats currently dropped entirely.
MARKITDOWN_EXTS = frozenset({".docx", ".pptx", ".xlsx", ".xls", ".epub"})


def is_markitdown_format(path: str) -> bool:
    """True if the file extension is one we route through markitdown."""
    if not isinstance(path, str):
        return False
    return os.path.splitext(path)[1].lower() in MARKITDOWN_EXTS


def load_markitdown():
    """Return the MarkItDown class, or raise a user-facing setup hint."""
    try:
        from markitdown import MarkItDown  # optional dependency
    except ImportError as exc:
        raise RuntimeError(MARKITDOWN_MISSING) from exc
    return MarkItDown


def _extract_docx_native(path: str) -> str | None:
    """Pure-Python .docx text extractor — no external deps.

    A .docx file is just a zip of XML. The body prose lives in <w:t> runs
    inside <w:p> paragraphs. Iterating with ElementTree (rather than
    re.findall) keeps paragraph breaks intact and lets the XML parser handle
    namespaces + entity unescaping. Loses tables, footnotes, images and
    list bullets — keeps ~95% of "summarize this doc" content, which is the
    case people hit when markitdown isn't installed.
    """
    import zipfile
    import xml.etree.ElementTree as ET

    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    try:
        with zipfile.ZipFile(path) as z:
            xml_bytes = z.read("word/document.xml")
    except (zipfile.BadZipFile, KeyError, OSError):
        return None
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return None
    paragraphs: list[str] = []
    for para in root.iter(f"{ns}p"):
        runs = [t.text or "" for t in para.iter(f"{ns}t")]
        line = "".join(runs).strip()
        if line:
            paragraphs.append(line)
    return "\n\n".join(paragraphs) if paragraphs else None


# Built-in readers (openpyxl / python-docx / python-pptx are core
# dependencies since file creation landed), used when markitdown is absent.
# Before, .xlsx and .pptx were dropped entirely without it.
NATIVE_MAX_ROWS_PER_SHEET = 2_000
NATIVE_MAX_CELL_CHARS = 500


def _md_cell(value) -> str:
    text = "" if value is None else str(value)
    text = text.replace("|", "\\|").replace("\n", " ").strip()
    return text[:NATIVE_MAX_CELL_CHARS]


def _md_table(rows: list[list]) -> list[str]:
    width = max((len(r) for r in rows), default=0)
    if not width:
        return []
    padded = [[_md_cell(c) for c in r] + [""] * (width - len(r)) for r in rows]
    out = ["| " + " | ".join(padded[0]) + " |", "|" + " --- |" * width]
    out += ["| " + " | ".join(r) + " |" for r in padded[1:]]
    return out


def _extract_xlsx_native(path: str) -> str | None:
    """Every sheet as a Markdown table (values, not formulas), row-capped."""
    try:
        from openpyxl import load_workbook
        wb = load_workbook(path, read_only=True, data_only=True)
    except Exception:
        return None
    parts: list[str] = []
    try:
        for ws in wb.worksheets:
            rows, truncated = [], False
            for i, row in enumerate(ws.iter_rows(values_only=True)):
                if i >= NATIVE_MAX_ROWS_PER_SHEET:
                    truncated = True
                    break
                if any(v not in (None, "") for v in row):
                    rows.append(list(row))
            if not rows:
                continue
            # Drop all-empty trailing columns read-only sheets often report.
            last = max(max((j for j, v in enumerate(r) if v not in (None, "")), default=-1) for r in rows)
            rows = [r[: last + 1] for r in rows]
            parts.append(f"## Sheet: {ws.title}")
            parts.extend(_md_table(rows))
            if truncated:
                parts.append(f"_(first {NATIVE_MAX_ROWS_PER_SHEET} rows shown)_")
            parts.append("")
    finally:
        wb.close()
    return "\n".join(parts).strip() or None


def _extract_pptx_native(path: str) -> str | None:
    """Slide titles, text, tables and speaker notes, in slide order."""
    try:
        from pptx import Presentation
        prs = Presentation(path)
    except Exception:
        return None
    parts: list[str] = []
    for n, slide in enumerate(prs.slides, start=1):
        title_shape = slide.shapes.title
        title = title_shape.text.strip() if title_shape is not None and title_shape.has_text_frame else ""
        title_id = title_shape.shape_id if title_shape is not None else None
        parts.append(f"## Slide {n}" + (f": {title}" if title else ""))
        for shape in slide.shapes:
            # python-pptx returns a new proxy per access, so compare ids.
            if shape.shape_id == title_id:
                continue
            if getattr(shape, "has_table", False) and shape.has_table:
                parts.extend(_md_table([[c.text for c in row.cells] for row in shape.table.rows]))
            elif shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    line = "".join(r.text for r in para.runs).strip()
                    if line:
                        parts.append(f"- {line}")
        if slide.has_notes_slide:
            notes = slide.notes_slide.notes_text_frame.text.strip()
            if notes:
                parts.append(f"Notes: {notes}")
        parts.append("")
    return "\n".join(parts).strip() or None


def _extract_docx_with_tables(path: str) -> str | None:
    """Paragraphs and tables in document order via python-docx."""
    try:
        from docx import Document
        from docx.table import Table
        from docx.text.paragraph import Paragraph
        doc = Document(path)
    except Exception:
        return None
    parts: list[str] = []
    for child in doc.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            para = Paragraph(child, doc)
            text = para.text.strip()
            if not text:
                continue
            style = (para.style.name if para.style is not None else "") or ""
            if style.startswith("Heading") and style[-1:].isdigit():
                parts.append("#" * min(int(style[-1]), 6) + " " + text)
            elif style == "Title":
                parts.append("# " + text)
            elif "List" in style:
                parts.append("- " + text)
            else:
                parts.append(text)
        elif tag == "tbl":
            parts.extend(_md_table([[c.text for c in row.cells] for row in Table(child, doc).rows]))
        parts.append("")
    return "\n".join(parts).strip() or None


_NATIVE_EXTRACTORS = {
    ".xlsx": _extract_xlsx_native,
    ".pptx": _extract_pptx_native,
    ".docx": _extract_docx_with_tables,
}


def convert_to_markdown(path: str) -> str | None:
    """Convert a document to Markdown text via markitdown.

    Returns the extracted Markdown, or ``None`` if markitdown is unavailable or
    the conversion fails — callers degrade gracefully rather than erroring.

    Fallback: when markitdown isn't installed and the file is a .docx, run
    the bundled pure-Python extractor so the most common case (Word docs)
    works out of the box. Other Office/EPUB formats still need markitdown.
    """
    try:
        markitdown_cls = load_markitdown()
    except RuntimeError:
        ext = os.path.splitext(path)[1].lower() if isinstance(path, str) else ""
        native = _NATIVE_EXTRACTORS.get(ext)
        text = native(path) if native else None
        if not text and ext == ".docx":
            text = _extract_docx_native(path)  # zip/XML fallback, no python-docx
        if text:
            logger.info("markitdown not installed — used built-in %s reader for %s", ext, path)
            return text
        logger.warning("markitdown not installed; cannot extract %s", path)
        return None
    try:
        result = markitdown_cls().convert(path)
        text = getattr(result, "text_content", None)
        if text is None:
            text = getattr(result, "markdown", None)
        return text
    except Exception as e:
        logger.warning("markitdown failed to convert %s: %s", path, e)
        return None
