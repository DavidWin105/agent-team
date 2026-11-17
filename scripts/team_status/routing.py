"""Sum the routing log per model (spec section 9). Cells not seen are counted, never estimated."""
import re
from collections import namedtuple

ModelTotals = namedtuple("ModelTotals", "runs tokens not_seen minutes findings kept")
Summary = namedtuple("Summary", "models unread problem", defaults=(None,))
COLUMNS = 12
EMPTY_CELLS = ("", "-")
# Only plain non-negative numbers are real counts or times; anything else is not read.
COUNT = re.compile(r"^\d+$")
# Tokens may carry thousands commas; minutes never do.
TOKENS_TEXT = re.compile(r"^\d{1,3}(,\d{3})*$|^\d+$")
TIME = re.compile(r"^\d+(\.\d+)?$")
ZERO = ModelTotals(0, 0, 0, 0.0, (0, 0, 0), 0)
# Column positions in the routing log table.
MODEL, TOKENS, MINUTES, FINDINGS, KEPT = 4, 5, 7, 8, 9


def summarize(path):
    """Answer per-model totals and the number of rows that could not be read."""
    try:
        with open(path, encoding="utf-8") as handle:
            rows = _table_rows(handle.read().splitlines())
    except (OSError, UnicodeDecodeError):
        return Summary({}, 0, "cannot be read")
    models = {}
    unread = 0
    for cells in rows:
        parsed = _parse_row(cells)
        if parsed is None:
            unread += 1
            continue
        model, totals = parsed
        models = {**models, model: _add(models.get(model, ZERO), totals)}
    return Summary(models, unread)


def _table_rows(lines):
    for start, line in enumerate(lines):
        if line.startswith("| Date"):
            rows = []
            for row in lines[start + 2:]:
                if not row.startswith("|"):
                    break
                rows.append([cell.strip() for cell in row.strip().strip("|").split("|")])
            return rows
    return []


def _parse_row(cells):
    if len(cells) < COLUMNS or cells[MODEL] in EMPTY_CELLS:
        return None
    try:
        tokens = _number(cells[TOKENS], TOKENS_TEXT, int)
        minutes = _number(cells[MINUTES], TIME, float)
        findings = _findings(cells[FINDINGS])
        kept = _number(cells[KEPT], COUNT, int)
    except ValueError:
        return None
    blank = cells[FINDINGS] == "" or cells[KEPT] == ""
    not_seen = 1 if tokens is None or minutes is None or blank else 0
    return cells[MODEL].lower(), ModelTotals(1, tokens or 0, not_seen, minutes or 0.0, findings, kept or 0)


def _number(cell, pattern, kind):
    if cell in EMPTY_CELLS:
        return None
    if not pattern.match(cell):
        raise ValueError(cell)
    return kind(cell.replace(",", ""))


def _findings(cell):
    if cell in EMPTY_CELLS:
        return (0, 0, 0)
    parts = cell.split("/")
    if len(parts) != 3 or not all(COUNT.match(part) for part in parts):
        raise ValueError(cell)
    return tuple(int(part) for part in parts)


def _add(total, row):
    return ModelTotals(
        total.runs + row.runs,
        total.tokens + row.tokens,
        total.not_seen + row.not_seen,
        total.minutes + row.minutes,
        tuple(a + b for a, b in zip(total.findings, row.findings)),
        total.kept + row.kept,
    )
