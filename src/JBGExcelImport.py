"""301k (asked 2026-11-26): an Excel workbook (.xlsx) as one CSV dataset per
chosen sheet.

``sheet_overview`` lists a workbook's sheets (name, rows, columns, header), and
``sheet_to_csv`` writes one sheet as a CSV file (UTF-8 with a byte-order mark,
semicolons), which the ordinary CSV upload then registers. The first row is the
header. Cells are read as Excel shows their values: formulas as their last
computed result, dates as ISO dates. Rows with no value are left out. Blank or
repeated header names get unique names, since a CSV dataset needs them.
Chart sheets have no rows and are not listed. The old .xls format is not read.
"""
from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path

DELIMITER = ";"
ENCODING = "utf-8-sig"


class ExcelRefused(ValueError):
    """The file cannot be read as an .xlsx workbook (the reason is a code)."""


def _open(path: Path):
    from openpyxl import load_workbook
    from openpyxl.utils.exceptions import InvalidFileException
    from zipfile import BadZipFile
    try:
        return load_workbook(path, read_only=True, data_only=True)
    except (InvalidFileException, BadZipFile, KeyError, OSError, ValueError):
        raise ExcelRefused("not_xlsx") from None


def _text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, dt.datetime):
        if value.time() == dt.time(0, 0):
            return value.date().isoformat()
        return value.isoformat(sep=" ", timespec="seconds")
    if isinstance(value, (dt.date, dt.time)):
        return value.isoformat()
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else repr(value)
    return str(value).strip()


def _rows(sheet):
    """The sheet's rows as text, trailing empty cells trimmed, empty rows left out."""
    for row in sheet.iter_rows(values_only=True):
        cells = [_text(value) for value in row]
        while cells and cells[-1] == "":
            cells.pop()
        if cells:
            yield cells


def _header(cells: list) -> list:
    names, seen = [], set()
    for i, cell in enumerate(cells, start=1):
        name = cell.strip() or f"Kolumn_{i}"
        base, n = name, 2
        while name.casefold() in seen:
            name, n = f"{base}_{n}", n + 1
        seen.add(name.casefold())
        names.append(name)
    return names


def sheet_overview(path: Path) -> list:
    """The workbook's sheets with rows: name, data rows, columns and header."""
    book = _open(Path(path))
    try:
        found = []
        for sheet in book.worksheets:
            rows = _rows(sheet)
            first = next(rows, None)
            if first is None:
                found.append({"sheet": sheet.title, "rows": 0, "columns": 0, "header": []})
                continue
            count = sum(1 for _ in rows)
            found.append({"sheet": sheet.title, "rows": count, "columns": len(first),
                          "header": _header(first)[:30]})
        return found
    finally:
        book.close()


def sheet_to_csv(path: Path, sheet: str, target: Path) -> int:
    """Write one sheet as a CSV file; returns the number of data rows."""
    book = _open(Path(path))
    try:
        if sheet not in book.sheetnames:
            raise ExcelRefused("no_sheet")
        worksheet = book[sheet]
        if not hasattr(worksheet, "iter_rows"):
            raise ExcelRefused("no_sheet")
        rows = list(_rows(worksheet))
        if len(rows) < 2:
            raise ExcelRefused("empty_sheet")
        # Values beyond the header's last cell get a column of their own.
        width = max(len(cells) for cells in rows)
        header = _header(rows[0] + [""] * (width - len(rows[0])))
        count = 0
        with Path(target).open("w", encoding=ENCODING, newline="") as stream:
            writer = csv.writer(stream, delimiter=DELIMITER, lineterminator="\r\n")
            writer.writerow(header)
            for cells in rows[1:]:
                writer.writerow(cells + [""] * (width - len(cells)))
                count += 1
        if count == 0:
            raise ExcelRefused("empty_sheet")
        return count
    finally:
        book.close()
