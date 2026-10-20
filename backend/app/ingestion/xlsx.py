"""Minimal read-only XLSX reader built on the standard library.

The project deliberately carries no ``pandas``/``openpyxl`` dependency, so
spreadsheets are parsed directly from the OOXML parts with :mod:`zipfile` and
:mod:`xml.etree`. Only the subset needed by the Phase 1 workbook is supported:
a single worksheet, shared strings, inline strings, and numeric/date cells.

Excel stores dates as serial day counts, so ``read_xlsx`` converts columns whose
header is declared as a date rather than guessing from the number format.
"""

from __future__ import annotations

import datetime as _dt
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterator

_MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_EXCEL_EPOCH = _dt.datetime(1899, 12, 30)

#: Columns treated as Excel serial dates, by header name. Explicit beats
#: inferring: a bare number in a text column must not become a date.
DATE_COLUMNS = frozenset({"mating_date", "estimated_delivery_date"})


def _column_index(ref: str) -> int:
    letters = "".join(ch for ch in ref if ch.isalpha()).upper()
    index = 0
    for ch in letters:
        index = index * 26 + (ord(ch) - ord("A") + 1)
    return index - 1


def _read_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    return [
        "".join(node.text or "" for node in si.iter(f"{_MAIN}t"))
        for si in root.findall(f"{_MAIN}si")
    ]


def _cell_value(cell: ET.Element, shared: list[str]) -> str:
    kind = cell.get("t")
    if kind == "inlineStr":
        return "".join(node.text or "" for node in cell.iter(f"{_MAIN}t"))
    value = cell.find(f"{_MAIN}v")
    if value is None or value.text is None:
        return ""
    if kind == "s":
        index = int(value.text)
        return shared[index] if 0 <= index < len(shared) else ""
    return value.text


def _serial_to_iso(raw: str) -> str:
    try:
        return (_EXCEL_EPOCH + _dt.timedelta(days=float(raw))).date().isoformat()
    except (TypeError, ValueError):
        return raw


def _row_cells(row: ET.Element, shared: list[str]) -> dict[int, str]:
    cells: dict[int, str] = {}
    for cell in row.findall(f"{_MAIN}c"):
        ref = cell.get("r") or ""
        cells[_column_index(ref)] = _cell_value(cell, shared)
    return cells


def read_xlsx(path: Path) -> list[dict[str, str]]:
    """Return the first worksheet as a list of dicts keyed by header name.

    Headers are lowercased with spaces folded to underscores so downstream code
    can address them as stable field names.
    """
    with zipfile.ZipFile(path) as archive:
        shared = _read_shared_strings(archive)
        sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        data = sheet.find(f"{_MAIN}sheetData")
        if data is None:
            return []
        rows = list(data.findall(f"{_MAIN}row"))
        if not rows:
            return []

        header_cells = _row_cells(rows[0], shared)
        width = max(header_cells) + 1
        headers = [
            (header_cells.get(i) or f"column_{i}").strip().lower().replace(" ", "_")
            for i in range(width)
        ]

        records: list[dict[str, str]] = []
        for row in rows[1:]:
            cells = _row_cells(row, shared)
            record = {
                headers[i]: (cells.get(i) or "").strip()
                for i in range(width)
                if headers[i]
            }
            for name in DATE_COLUMNS & record.keys():
                record[name] = _serial_to_iso(record[name])
            records.append(record)
        return records


def iter_csv(path: Path) -> Iterator[dict[str, str]]:
    """Stream a UTF-8 CSV as dicts, tolerating a BOM."""
    import csv

    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        for record in csv.DictReader(handle):
            yield {key: (value or "").strip() for key, value in record.items()}
