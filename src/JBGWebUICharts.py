"""Small SVG charts drawn on the server (revision 299k).

Agreed 2026-11-13: the Overview's charts are drawn on the server, so they work
offline and in both languages, with no chart library. Colours come from CSS
classes (jbg.css). Every chart has a title and a text alternative; with no
data it shows a placeholder text instead of empty axes.
"""
from __future__ import annotations

from html import escape

WIDTH, HEIGHT = 520, 180
LEFT, RIGHT, TOP, BOTTOM = 44, 8, 10, 26


def _frame(body: str, label: str, height: int = HEIGHT) -> str:
    return (f'<svg class="chart" viewBox="0 0 {WIDTH} {height}" role="img" '
            f'aria-label="{escape(label)}" preserveAspectRatio="xMinYMin meet">'
            f"<title>{escape(label)}</title>{body}</svg>")


def _empty(label: str, text: str) -> str:
    return _frame(f'<text class="chart-empty" x="{WIDTH / 2}" y="{HEIGHT / 2}" '
                  f'text-anchor="middle">{escape(text)}</text>', label)


def _nice(value: float) -> float:
    """A round top for the axis (1, 2, 5 times a power of ten)."""
    if value <= 0:
        return 1.0
    power = 10 ** len(str(int(value))) / 10
    for step in (1, 2, 5, 10):
        if value <= step * power:
            return step * power
    return 10 * power


def _number(value: float, language: str) -> str:
    text = f"{value:,.0f}" if abs(value) >= 10 or value == int(value) else f"{value:.2f}"
    if language == "sv":
        text = text.replace(",", "\u00a0").replace(".", ",")
    return text


def _axis(top: float, language: str, height: int = HEIGHT) -> str:
    inner = height - TOP - BOTTOM
    parts = []
    for i in range(3):
        value = top * i / 2
        y = TOP + inner - inner * i / 2
        parts.append(f'<line class="chart-grid" x1="{LEFT}" x2="{WIDTH - RIGHT}" y1="{y:.1f}" '
                     f'y2="{y:.1f}"/><text class="chart-tick" x="{LEFT - 6}" y="{y + 4:.1f}" '
                     f'text-anchor="end">{_number(value, language)}</text>')
    return "".join(parts)


def week_bars(weeks: list, series: list, *, label: str, empty: str, week_label,
              language: str) -> str:
    """Stacked bars per week. ``series``: [(key, css class, legend text)]."""
    totals = [sum(w[key] for key, _, _ in series) for w in weeks]
    if not any(totals):
        return _empty(label, empty)
    top = _nice(max(totals))
    if top < 10 and top % 2:
        top *= 2                                   # whole numbers on the middle line
    inner_h, inner_w = HEIGHT - TOP - BOTTOM, WIDTH - LEFT - RIGHT
    slot = inner_w / len(weeks)
    parts = [_axis(top, language)]
    for i, week in enumerate(weeks):
        x, base = LEFT + i * slot + slot * 0.18, TOP + inner_h
        for key, css, legend in series:
            height = inner_h * week[key] / top
            if height > 0:
                base -= height
                parts.append(f'<rect class="{css}" x="{x:.1f}" y="{base:.1f}" '
                             f'width="{slot * 0.64:.1f}" height="{height:.1f}">'
                             f"<title>{escape(week_label(week['week']))}: {escape(legend)} "
                             f"{week[key]}</title></rect>")
        if i % 3 == 0 or i == len(weeks) - 1:
            parts.append(f'<text class="chart-tick" x="{x + slot * 0.32:.1f}" y="{HEIGHT - 8}" '
                         f'text-anchor="middle">{escape(week_label(week["week"]))}</text>')
    return _frame("".join(parts), label)


def project_bars(items: list, *, label: str, empty: str, language: str) -> str:
    """Horizontal bars of rows processed per project, the open one highlighted."""
    shown = items[:8]
    if not any(item["rows"] for item in shown):
        return _empty(label, empty)
    top = max(item["rows"] for item in shown)
    row_h, name_w = 22, 150
    height = TOP + len(shown) * row_h + 6
    parts = []
    for i, item in enumerate(shown):
        y = TOP + i * row_h
        width = (WIDTH - name_w - 70) * item["rows"] / top if top else 0
        css = "chart-hl" if item["open"] else "chart-bar"
        name = item["name"] if len(item["name"]) <= 22 else item["name"][:21] + "…"
        parts.append(f'<text class="chart-tick{" chart-strong" if item["open"] else ""}" '
                     f'x="{name_w - 6}" y="{y + 14}" text-anchor="end">{escape(name)}</text>'
                     f'<rect class="{css}" x="{name_w}" y="{y + 3}" width="{max(width, 1):.1f}" '
                     f'height="{row_h - 8}"/><text class="chart-tick" x="{name_w + width + 6:.1f}" '
                     f'y="{y + 14}">{_number(item["rows"], language)}</text>')
    return _frame("".join(parts), label, height)


def quality_line(points: list, average, *, label: str, empty: str, average_label: str,
                 point_label, language: str) -> str:
    """The metric per training run (oldest first) with the average of the last three."""
    if not points:
        return _empty(label, empty)
    values = [p["value"] for p in points]
    low = min(0.0, min(values))
    top = 1.0 if max(values) <= 1.0 else _nice(max(values))
    inner_h, inner_w = HEIGHT - TOP - BOTTOM, WIDTH - LEFT - RIGHT

    def y(value):
        return TOP + inner_h - inner_h * (value - low) / (top - low)

    def x(i):
        return LEFT + (inner_w * (i + 0.5) / len(points))
    parts = []
    for fraction in (0, 0.5, 1):
        value = low + (top - low) * fraction
        parts.append(f'<line class="chart-grid" x1="{LEFT}" x2="{WIDTH - RIGHT}" '
                     f'y1="{y(value):.1f}" y2="{y(value):.1f}"/><text class="chart-tick" '
                     f'x="{LEFT - 6}" y="{y(value) + 4:.1f}" text-anchor="end">'
                     f"{_number(value, language)}</text>")
    if average is not None:
        parts.append(f'<line class="chart-avg" x1="{LEFT}" x2="{WIDTH - RIGHT}" '
                     f'y1="{y(average):.1f}" y2="{y(average):.1f}"><title>'
                     f"{escape(average_label)} {_number(average, language)}</title></line>")
    if len(points) > 1:
        path = " ".join(f"{x(i):.1f},{y(p['value']):.1f}" for i, p in enumerate(points))
        parts.append(f'<polyline class="chart-line" points="{path}"/>')
    for i, p in enumerate(points):
        parts.append(f'<circle class="chart-dot" cx="{x(i):.1f}" cy="{y(p["value"]):.1f}" r="3.5">'
                     f"<title>{escape(point_label(p))}: {_number(p['value'], language)}</title>"
                     f"</circle>")
    return _frame("".join(parts), label)
