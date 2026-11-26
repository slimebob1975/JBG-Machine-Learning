"""301k (asked 2026-11-26): an Excel workbook (.xlsx) as one CSV dataset per
chosen sheet, each with its own name and role. Also: a stored file name made
safe from a dataset's name (an en dash or & was refused, also for corrections
and the 301i ID column)."""
import datetime as dt
import io
import re
from pathlib import Path

import pytest

from JBGExcelImport import ExcelRefused, sheet_overview, sheet_to_csv
from Storage.CSVDatasetCatalog import csv_file_name_for

ROOT = Path(__file__).resolve().parent.parent


def _workbook() -> bytes:
    from openpyxl import Workbook
    book = Workbook()
    train = book.active
    train.title = "Träning"
    train.append(["Id", "System", "", "Belopp", "Datum", "Risknivå"])
    for i in range(1, 31):
        train.append([i, f"System {i}", "x", i * 1.5, dt.datetime(2026, 1, 1 + i % 28),
                      "Hög" if i % 3 == 0 else "Låg"])
    train.append([None] * 6)                              # an empty row
    prediction = book.create_sheet("Prediktion")
    prediction.append(["Id", "System", "", "Belopp", "Datum"])
    for i in range(31, 36):
        prediction.append([i, f"System {i}", "y", i * 1.5, dt.date(2026, 2, 1)])
    book.create_sheet("Tom")
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def test_the_sheets_and_their_csv(tmp_path):
    book = tmp_path / "b.xlsx"
    book.write_bytes(_workbook())
    sheets = {s["sheet"]: s for s in sheet_overview(book)}
    assert sheets["Träning"]["rows"] == 30 and sheets["Tom"]["rows"] == 0
    assert sheets["Träning"]["header"] == ["Id", "System", "Kolumn_3", "Belopp", "Datum", "Risknivå"]
    target = tmp_path / "t.csv"
    assert sheet_to_csv(book, "Träning", target) == 30
    raw = target.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    lines = raw.decode("utf-8-sig").splitlines()
    assert lines[0] == "Id;System;Kolumn_3;Belopp;Datum;Risknivå"
    assert lines[1] == "1;System 1;x;1.5;2026-01-02;Låg" and lines[2].split(";")[3] == "3"
    for sheet, code in (("Tom", "empty_sheet"), ("Saknas", "no_sheet")):
        with pytest.raises(ExcelRefused, match=code):
            sheet_to_csv(book, sheet, target)
    (tmp_path / "x.xlsx").write_bytes(b"\xd0\xcf\x11\xe0 an old .xls")
    with pytest.raises(ExcelRefused, match="not_xlsx"):
        sheet_overview(tmp_path / "x.xlsx")


def test_safe_stored_file_names():
    assert csv_file_name_for("Riskkarta – Träning") == "Riskkarta _ Träning.csv"
    assert csv_file_name_for("A&B: test") == "A_B_ test.csv"
    assert csv_file_name_for("") == "dataset.csv"
    assert len(csv_file_name_for("x" * 300)) == 120


def test_the_two_steps_in_the_form(tmp_path):
    pytest.importorskip("fastapi")
    from test_revision_288a_project_runs import _client
    with _client(tmp_path) as client:
        project = client.post("/api/projects", json={"name": "P", "source": "csv"}).json()["project_id"]
        client.post(f"/ui/projects/{project}/open")
        panel = client.get("/ui/dataset").text
        first = client.post("/ui/dataset/excel", follow_redirects=False,
                            files={"file": ("Riskkarta.xlsx", _workbook(), "application/octet-stream")})
        token = first.headers["location"].split("excel=")[1]
        choose = client.get(first.headers["location"]).text
        none = client.post(f"/ui/dataset/excel/{token}", data={}, follow_redirects=False)
        added = client.post(f"/ui/dataset/excel/{token}", follow_redirects=False, data={
            "sheet_0": "1", "name_0": "Riskkarta – Träning", "role_0": "training",
            "sheet_1": "1", "name_1": "Riskkarta – Prediktion", "role_1": "prediction"})
        result = client.get(added.headers["location"]).text
        again = client.post(f"/ui/dataset/excel/{token}", follow_redirects=False, data={
            "sheet_0": "1", "name_0": "Riskkarta – Träning", "role_0": "training"})
        again_page = client.get(again.headers["location"]).text
        listed = {d["name"]: d["role"] for d in client.get(f"/api/projects/{project}/datasets").json()}
        gone = client.get("/ui/dataset?excel=" + "0" * 32).text
        old = client.post("/ui/dataset/excel", follow_redirects=False,
                          files={"file": ("gammal.xls", b"\xd0\xcf\x11\xe0 old", "application/vnd.ms-excel")})
    assert "Lägg till från Excel" in panel and 'action="/ui/dataset/excel"' in panel
    assert "Flikar i Riskkarta.xlsx" in choose and "Riskkarta – Träning" in choose
    assert re.search(r'name="role_1"[^>]*>.*?<option value="prediction" selected', choose, re.S)
    assert re.search(r'name="sheet_2" value="1" aria-label="Tom"\s+disabled', choose)
    assert "message=excel_none_chosen" in none.headers["location"]
    assert "message=excel_added" in added.headers["location"]
    assert result.count('class="badge b-ok"') == 2
    assert listed == {"Riskkarta – Träning": "training", "Riskkarta – Prediktion": "prediction"}
    assert "message=excel_partly" in again.headers["location"]
    assert "Ett dataset med det namnet finns redan i projektet." in again_page
    assert "Arbetsboken finns inte längre. Välj filen igen." in gone
    assert "message=excel_not_xlsx" in old.headers["location"]


def test_the_api_and_another_owner(tmp_path):
    pytest.importorskip("fastapi")
    from test_revision_288a_project_runs import _client
    with _client(tmp_path) as client:
        project = client.post("/api/projects", json={"name": "P", "source": "csv"}).json()["project_id"]
        read = client.post(f"/api/projects/{project}/datasets/excel",
                           files={"file": ("b.xlsx", _workbook(), "application/octet-stream")})
        token = read.json()["token"]
        added = client.post(f"/api/projects/{project}/datasets/excel/{token}", json={
            "sheets": [{"sheet": "Träning", "name": "T", "role": "training"},
                       {"sheet": "Tom", "name": "E", "role": "training"}]})
        empty = client.post(f"/api/projects/{project}/datasets/excel/{token}", json={"sheets": []})
    assert read.status_code == 201 and [s["sheet"] for s in read.json()["sheets"]] == \
        ["Träning", "Prediktion", "Tom"]
    results = added.json()["results"]
    assert results[0]["rows"] == 30 and results[0]["id_candidates"][0] == "Id"
    assert results[1]["error"] == "empty_sheet"
    assert empty.status_code == 422
    # The workbook is kept per owner: another owner's folder never has it.
    from types import SimpleNamespace
    from JBGDatasetService import DatasetService
    holder = SimpleNamespace(EXCEL_ROOT=DatasetService.EXCEL_ROOT)
    assert DatasetService._excel_folder(holder, "someone") != \
        DatasetService._excel_folder(holder, "developer")


def test_requirements_and_guides():
    assert "\nopenpyxl\n" in (ROOT / "requirements.txt").read_text(encoding="utf-8")
    pins = (ROOT / "constraints-tested.txt").read_text(encoding="utf-8")
    assert "openpyxl==3.1.5" in pins and "et_xmlfile==2.0.0" in pins
    sv = " ".join((ROOT / "docs" / "user_guide.sv.md").read_text(encoding="utf-8").split())
    assert "Med **Lägg till från Excel** väljer du en arbetsbok (.xlsx)" in sv
