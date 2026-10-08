"""Charts for src/file_builder.py (plan v2 §7, report visualisation).

One chart spec for every format:

    {"type": "chart", "kind": "bar", "title": "Revenue by region",
     "categories": ["North", "South"],
     "series": [{"name": "2025", "values": [120, 80]},
                {"name": "2026", "values": [140, 85]}]}

``kind`` is bar (vertical), barh (horizontal), line or pie (first series
only). Excel, PowerPoint and PDF get native charts people can edit or that
stay sharp when zoomed; Word has no chart API in python-docx, so it gets a
PNG drawn with Pillow (already installed with reportlab).

Spreadsheets draw from the sheet itself: ``{"kind": "bar", "x": 0, "y": [1, 2]}``
on a sheet's ``charts`` list uses column 0 as categories and columns 1-2 as
series (0-based, header row gives the names; defaults: x=0, y=the rest).
"""
from __future__ import annotations

import io
import math
from dataclasses import dataclass
from typing import Any

KINDS = ("bar", "barh", "line", "pie")
MAX_CATEGORIES = 500
MAX_SERIES = 12
MAX_CHARTS_PER_SHEET = 20

# Colour-blind-safe categorical palette (Okabe-Ito, reordered for contrast).
PALETTE = ["#0072B2", "#E69F00", "#009E73", "#D55E00", "#56B4E9", "#CC79A7",
           "#F0E442", "#000000", "#999999", "#882255", "#44AA99", "#117733"]


class ChartSpecError(ValueError):
    pass


@dataclass
class Chart:
    kind: str
    title: str
    categories: list[str]
    series: list[tuple[str, list[float | None]]]


def _num(v: Any, where: str) -> float | None:
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        raise ChartSpecError(f"{where}: values must be numbers")
    if isinstance(v, (int, float)):
        if isinstance(v, float) and not math.isfinite(v):
            return None
        return v
    try:
        return float(str(v).replace(",", "").strip())
    except ValueError:
        raise ChartSpecError(f"{where}: {v!r} is not a number") from None


def kind_of(spec: dict, where: str) -> str:
    kind = str(spec.get("kind") or spec.get("chart") or "bar").strip().lower()
    if kind == "column":
        kind = "bar"
    if kind not in KINDS:
        raise ChartSpecError(f"{where}: kind must be one of {', '.join(KINDS)}")
    return kind


def parse(spec: Any, where: str = "chart") -> Chart:
    """Validate an inline chart spec (categories + series)."""
    if not isinstance(spec, dict):
        raise ChartSpecError(f"{where}: must be an object")
    kind = kind_of(spec, where)
    cats = spec.get("categories")
    series = spec.get("series")
    if not isinstance(cats, list) or not cats:
        raise ChartSpecError(f"{where}: 'categories' must be a non-empty list")
    if len(cats) > MAX_CATEGORIES:
        raise ChartSpecError(f"{where}: more than {MAX_CATEGORIES} categories")
    if isinstance(series, dict):
        series = [series]
    if not isinstance(series, list) or not series:
        raise ChartSpecError(f"{where}: 'series' must be a non-empty list of {{name, values}}")
    if len(series) > MAX_SERIES:
        raise ChartSpecError(f"{where}: more than {MAX_SERIES} series")
    out = []
    for i, s in enumerate(series):
        if not isinstance(s, dict) or not isinstance(s.get("values"), list):
            raise ChartSpecError(f"{where}: series {i} needs 'values' (a list)")
        vals = [_num(v, f"{where} series {i}") for v in s["values"]]
        if len(vals) != len(cats):
            raise ChartSpecError(f"{where}: series {i} has {len(vals)} values for {len(cats)} categories")
        out.append((str(s.get("name") or f"Series {i + 1}")[:120], vals))
    if kind == "pie":
        out = out[:1]
        if any(v is not None and v < 0 for v in out[0][1]):
            raise ChartSpecError(f"{where}: pie values cannot be negative")
    return Chart(kind, str(spec.get("title") or "")[:300], [str(c)[:120] for c in cats], out)


def sheet_columns(spec: dict, header: list[Any], where: str) -> tuple[str, int, list[int]]:
    """Validate a spreadsheet chart that points at sheet columns."""
    if not isinstance(spec, dict):
        raise ChartSpecError(f"{where}: must be an object")
    kind = kind_of(spec, where)
    width = len(header)
    x = spec.get("x", 0)
    y = spec.get("y")
    if y is None:
        y = [c for c in range(width) if c != x]
    if isinstance(y, int):
        y = [y]
    cols = [x, *y] if isinstance(y, list) else None
    if not cols or not all(isinstance(c, int) and not isinstance(c, bool) and 0 <= c < width for c in cols):
        raise ChartSpecError(f"{where}: x and y must be column numbers from 0 to {width - 1}")
    if not y or len(y) > MAX_SERIES:
        raise ChartSpecError(f"{where}: y needs 1 to {MAX_SERIES} columns")
    return kind, x, (y[:1] if kind == "pie" else y)


# ── PNG (Word) ─────────────────────────────────────────────────────────────

def _font(size: int):
    from PIL import ImageFont
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow < 10.1
        return ImageFont.load_default()


def _fmt(v: float) -> str:
    if abs(v) >= 1e9:
        return f"{v / 1e9:.1f}B"
    if abs(v) >= 1e6:
        return f"{v / 1e6:.1f}M"
    if abs(v) >= 1e4:
        return f"{v / 1e3:.0f}k"
    return f"{v:g}"


def _nice_range(lo: float, hi: float) -> tuple[float, float, float]:
    lo, hi = min(lo, 0.0), max(hi, 0.0)
    if hi == lo:
        hi = lo + 1
    raw = (hi - lo) / 5
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)
    return math.floor(lo / step) * step, math.ceil(hi / step) * step, step


def _short(text: str, n: int) -> str:
    return text if len(text) <= n else text[: n - 1] + "…"


def render_png(chart: Chart, width: int = 1400, height: int = 800) -> bytes:
    """Draw ``chart`` as a PNG. Plain and readable; not a plotting library."""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (width, height), "white")
    d = ImageDraw.Draw(img)
    ink, grid, muted = (31, 35, 41), (225, 228, 232), (95, 102, 114)
    title_f, label_f = _font(34), _font(22)
    top = 30
    if chart.title:
        d.text((width / 2, top), _short(chart.title, 80), fill=ink, font=title_f, anchor="ma")
        top += 60
    colours = PALETTE

    # Legend along the bottom when there is more than one series (or a pie).
    names = chart.categories if chart.kind == "pie" else [n for n, _ in chart.series]
    legend_h = 0
    if chart.kind == "pie" or len(chart.series) > 1:
        x, y, row_h = 40, height - 50, 40
        items = []
        for i, name in enumerate(names[:24]):
            w = 30 + d.textlength(_short(name, 30), font=label_f) + 30
            if x + w > width - 40:
                x, y = 40, y - row_h
            items.append((x, y, i, name))
            x += w
        legend_h = height - y + 10
        for x, y, i, name in items:
            d.rectangle([x, y + 4, x + 20, y + 24], fill=colours[i % len(colours)])
            d.text((x + 28, y + 2), _short(name, 30), fill=ink, font=label_f)

    if chart.kind == "pie":
        vals = [v or 0 for v in chart.series[0][1]]
        total = sum(vals) or 1
        size = min(width - 120, height - top - legend_h - 40)
        cx, cy = width / 2, top + 20 + size / 2
        box = [cx - size / 2, cy - size / 2, cx + size / 2, cy + size / 2]
        start = -90.0
        for i, v in enumerate(vals):
            sweep = 360 * v / total
            if sweep > 0:
                d.pieslice(box, start, start + sweep, fill=colours[i % len(colours)], outline="white", width=3)
                if sweep > 12:
                    mid = math.radians(start + sweep / 2)
                    r = size * 0.33
                    d.text((cx + r * math.cos(mid), cy + r * math.sin(mid)), f"{100 * v / total:.0f}%",
                           fill="white", font=label_f, anchor="mm")
            start += sweep
        return _png(img)

    values = [v for _, vals in chart.series for v in vals if v is not None]
    lo, hi, step = _nice_range(min(values, default=0), max(values, default=1))
    horizontal = chart.kind == "barh"
    left = 110 if not horizontal else 40 + min(260, max(d.textlength(_short(c, 24), font=label_f)
                                                        for c in chart.categories) + 20)
    right, bottom = width - 40, height - legend_h - (70 if not horizontal else 50)
    n = len(chart.categories)

    def scale(v: float) -> float:  # value -> pixel along the value axis
        if horizontal:
            return left + (v - lo) / (hi - lo) * (right - left)
        return bottom - (v - lo) / (hi - lo) * (bottom - top)

    t = lo
    while t <= hi + step / 2:
        p = scale(t)
        if horizontal:
            d.line([p, top, p, bottom], fill=grid, width=2)
            d.text((p, bottom + 10), _fmt(t), fill=muted, font=label_f, anchor="ma")
        else:
            d.line([left, p, right, p], fill=grid, width=2)
            d.text((left - 12, p), _fmt(t), fill=muted, font=label_f, anchor="rm")
        t += step
    zero = scale(0)
    span = ((bottom - top) if horizontal else (right - left)) / n
    label_every = max(1, math.ceil(n / (12 if not horizontal else 30)))

    for ci, cat in enumerate(chart.categories):
        centre = (top if horizontal else left) + span * (ci + 0.5)
        if ci % label_every == 0:
            if horizontal:
                d.text((left - 12, centre), _short(cat, 24), fill=ink, font=label_f, anchor="rm")
            else:
                d.text((centre, bottom + 12), _short(cat, max(4, int(span / 12))), fill=ink, font=label_f,
                       anchor="ma")

    if chart.kind == "line":
        for si, (_, vals) in enumerate(chart.series):
            colour = colours[si % len(colours)]
            pts, run = [], []
            for i, v in enumerate(vals + [None]):
                if v is None:  # a gap in the data is a gap in the line
                    if len(run) > 1:
                        d.line(run, fill=colour, width=5, joint="curve")
                    run = []
                    continue
                run.append((left + span * (i + 0.5), scale(v)))
                pts.append(run[-1])
            for x, y in pts if n <= 60 else []:
                d.ellipse([x - 6, y - 6, x + 6, y + 6], fill=colour)
    else:
        k = len(chart.series)
        band = span * 0.8
        bar = band / k
        for si, (_, vals) in enumerate(chart.series):
            colour = colours[si % len(colours)]
            for ci, v in enumerate(vals):
                if v is None:
                    continue
                start = (top if horizontal else left) + span * ci + (span - band) / 2 + bar * si
                a, b = sorted((zero, scale(v)))
                box = [a, start, b, start + bar - 2] if horizontal else [start, a, start + bar - 2, b]
                d.rectangle(box, fill=colour)
    axis = [left, top, left, bottom] if not horizontal else [left, bottom, right, bottom]
    d.line(axis, fill=muted, width=2)
    d.line([zero, top, zero, bottom] if horizontal else [left, zero, right, zero], fill=muted, width=2)
    return _png(img)


def _png(img) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# ── PDF (reportlab, vector) ────────────────────────────────────────────────

def pdf_drawing(chart: Chart, width: float, height: float):
    from reportlab.graphics.charts.barcharts import HorizontalBarChart, VerticalBarChart
    from reportlab.graphics.charts.legends import Legend
    from reportlab.graphics.charts.linecharts import HorizontalLineChart
    from reportlab.graphics.charts.piecharts import Pie
    from reportlab.graphics.shapes import Drawing, String
    from reportlab.lib import colors

    cols = [colors.HexColor(c) for c in PALETTE]
    d = Drawing(width, height)
    top_pad = 22 if chart.title else 6
    if chart.title:
        d.add(String(width / 2, height - 14, _short(chart.title, 90), textAnchor="middle",
                     fontName="Helvetica-Bold", fontSize=11))
    many = chart.kind == "pie" or len(chart.series) > 1
    legend_w = 120 if many else 0
    plot_w, plot_h = width - legend_w - 60, height - top_pad - 40

    if chart.kind == "pie":
        p = Pie()
        size = min(plot_w, plot_h)
        p.x, p.y, p.width, p.height = 30, 20, size, size
        p.data = [v or 0 for v in chart.series[0][1]]
        p.slices.strokeColor = colors.white
        for i in range(len(p.data)):
            p.slices[i].fillColor = cols[i % len(cols)]
        d.add(p)
        pairs = [(cols[i % len(cols)], _short(c, 22)) for i, c in enumerate(chart.categories[:20])]
    else:
        if chart.kind == "line":
            c = HorizontalLineChart()
        elif chart.kind == "barh":
            c = HorizontalBarChart()
        else:
            c = VerticalBarChart()
        c.x, c.y, c.width, c.height = 45, 30, plot_w, plot_h
        c.data = [tuple(v for v in vals) for _, vals in chart.series]
        cat_axis = c.categoryAxis
        cat_axis.categoryNames = [_short(x, 14) for x in chart.categories]
        cat_axis.labels.fontSize = 7
        cat_axis.labels.fontName = "Helvetica"
        cat_axis.labelAxisMode = "low"  # labels stay at the edge when values go negative
        if chart.kind == "barh":
            cat_axis.reverseDirection = 1  # first category at the top, as it is read
        elif len(chart.categories) > 8:
            cat_axis.labels.angle = 30
            cat_axis.labels.boxAnchor = "ne"
        vals = [v for _, vs in chart.series for v in vs if v is not None]
        lo, hi, step = _nice_range(min(vals, default=0), max(vals, default=1))
        va = c.valueAxis
        va.valueMin, va.valueMax, va.valueStep = lo, hi, step
        va.labels.fontSize = 7
        va.labels.fontName = "Helvetica"
        va.labelTextFormat = _fmt
        va.visibleGrid = 1
        va.gridStrokeColor = colors.HexColor("#e1e4e8")
        target = c.lines if chart.kind == "line" else c.bars
        for i in range(len(chart.series)):
            if chart.kind == "line":
                target[i].strokeColor = cols[i % len(cols)]
                target[i].strokeWidth = 1.5
            else:
                target[i].fillColor = cols[i % len(cols)]
                target[i].strokeColor = None
        d.add(c)
        pairs = [(cols[i % len(cols)], _short(n, 22)) for i, (n, _) in enumerate(chart.series)]
    if many:
        lg = Legend()
        lg.x, lg.y = width - legend_w + 6, height - top_pad - 10
        lg.alignment = "right"
        lg.fontSize = 7
        lg.fontName = "Helvetica"
        lg.strokeColor = None
        lg.colorNamePairs = pairs
        lg.columnMaximum = 20
        d.add(lg)
    return d


# ── PowerPoint (python-pptx, native) ──────────────────────────────────────

def add_pptx_chart(slide, chart: Chart, x, y, cx, cy) -> None:
    from pptx.chart.data import CategoryChartData
    from pptx.dml.color import RGBColor
    from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION

    data = CategoryChartData()
    data.categories = chart.categories
    for name, vals in chart.series:
        data.add_series(name, vals)
    kind = {"bar": XL_CHART_TYPE.COLUMN_CLUSTERED, "barh": XL_CHART_TYPE.BAR_CLUSTERED,
            "line": XL_CHART_TYPE.LINE_MARKERS, "pie": XL_CHART_TYPE.PIE}[chart.kind]
    gf = slide.shapes.add_chart(kind, x, y, cx, cy, data)
    ch = gf.chart
    ch.has_legend = chart.kind == "pie" or len(chart.series) > 1
    if ch.has_legend:
        ch.legend.position = XL_LEGEND_POSITION.BOTTOM
        ch.legend.include_in_layout = False
    if chart.kind != "pie":
        from pptx.enum.chart import XL_TICK_LABEL_POSITION
        # Category labels at the edge of the plot, not on the zero line under negative bars.
        ch.category_axis.tick_label_position = XL_TICK_LABEL_POSITION.LOW
    if chart.kind == "pie":
        for i, point in enumerate(ch.plots[0].series[0].points):
            point.format.fill.solid()
            point.format.fill.fore_color.rgb = RGBColor.from_string(PALETTE[i % len(PALETTE)][1:])
    else:
        for i, s in enumerate(ch.plots[0].series):
            fmt = s.format.line if chart.kind == "line" else s.format.fill
            if chart.kind == "line":
                fmt.color.rgb = RGBColor.from_string(PALETTE[i % len(PALETTE)][1:])
            else:
                fmt.solid()
                fmt.fore_color.rgb = RGBColor.from_string(PALETTE[i % len(PALETTE)][1:])


# ── Excel (openpyxl, native, drawn from sheet columns) ─────────────────────

def add_xlsx_chart(ws, kind: str, x: int, y: list[int], n_rows: int, title: str, anchor: str) -> None:
    from openpyxl.chart import BarChart, LineChart, PieChart, Reference

    if kind == "pie":
        ch = PieChart()
    elif kind == "line":
        ch = LineChart()
    else:
        ch = BarChart()
        ch.type = "bar" if kind == "barh" else "col"
    if title:
        ch.title = title[:300]
    ch.width, ch.height = 18, 9
    cats = Reference(ws, min_col=x + 1, min_row=2, max_row=n_rows)
    for col in y:
        ch.add_data(Reference(ws, min_col=col + 1, min_row=1, max_row=n_rows), titles_from_data=True)
    ch.set_categories(cats)
    if kind == "line":
        for s in ch.series:
            s.smooth = False  # straight segments: a smoothed line invents values between points
    if kind != "pie" and len(y) == 1:
        ch.legend = None
    ws.add_chart(ch, anchor)
