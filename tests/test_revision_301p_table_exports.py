"""301p (asked 2026-11-26): every view and subview exports its tables as CSV or
Excel, with all rows (decided 2026-11-26): Excel a sheet per table; CSV the
tables one after another under their titles, semicolons, UTF-8 with a BOM and
decimal commas. The Dark Numbers view gives the whole calculation."""
import io
import json
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from JBGWebUIExport import EXPORTERS, tables_to_csv, tables_to_xlsx

pytest.importorskip("fastapi")
ROOT = Path(__file__).resolve().parent.parent


def test_the_formats():
    tables = [{"title": "A", "columns": ["x", "y"], "rows": [[1.5, "t"], [2.0, None], [True, 3]]},
              {"title": "B", "columns": ["z"], "rows": [["åäö"]]}]
    raw = tables_to_csv(tables)
    assert raw.startswith(b"\xef\xbb\xbf")
    assert raw.decode("utf-8-sig").splitlines() == ["A", "x;y", "1,5;t", "2;", "Ja;3", "",
                                                    "B", "z", "åäö"]
    from openpyxl import load_workbook
    book = load_workbook(io.BytesIO(tables_to_xlsx(tables)))
    assert [ws.title for ws in book.worksheets] == ["A", "B"]
    assert [c.value for c in book["A"][2]] == [1.5, "t"]           # numbers stay numbers


def test_every_tab_has_an_exporter_and_the_buttons():
    # 301s: no exporters for the left-panel lists (Projects, Overview).
    assert set(EXPORTERS) == {"results.html", "dataset.html", "run.html", "models.html",
                              "prediction.html", "history.html", "configuration.html"}
    for name in EXPORTERS:
        assert '{% include "_export.html" %}' in (ROOT / "src/web/templates" / name).read_text(
            encoding="utf-8"), name


def test_the_tabs_export(tmp_path):
    from openpyxl import load_workbook
    from test_revision_288a_project_runs import _client
    from test_revision_301c_run_history import _two_versions
    with _client(tmp_path) as client:
        project, dataset, configuration, first, second = _two_versions(client)
        page = client.get(f"/ui/dataset?dataset={dataset}&view=profile").text
        profile = client.get(f"/ui/dataset?dataset={dataset}&view=profile&export=xlsx")
        history = client.get(f"/ui/history?compare={first}&compare={second}&export=csv")
        settings = client.get(f"/ui/configuration?configuration={configuration}&export=xlsx")
    # 301r: one Export button, in the format chosen under Settings (Excel by default).
    assert "Exportera (Excel)" in page and "export=xlsx" in page
    sheets = load_workbook(io.BytesIO(profile.content)).sheetnames
    assert sheets == ["Profil"]                                     # 301s: not the list
    assert "Profil" in profile.headers["content-disposition"] or "Profil" in \
        profile.headers["content-disposition"].encode().decode("unicode_escape")
    text = history.content.decode("utf-8-sig")
    assert text.startswith("Körning 1\r\n") and "Inställningar som skiljer sig" in text
    assert "Körningar\r\n" not in text                            # 301s: not the list
    rows = load_workbook(io.BytesIO(settings.content))["Inställningar"]
    assert rows.max_row > 20


def test_dark_numbers_and_all_rows(tmp_path):
    from openpyxl import load_workbook
    from JBGDarkNumberRecord import build
    from test_revision_299b_csv_reclassification import _client, _setting
    from test_revision_299x_dark_number_record import CALCULATIONS, CONFIG
    record = build(CONFIG, pd.DataFrame(), {"random_state": 42})
    with _client(tmp_path) as client:
        s = _setting(client, tmp_path)
        csvs = s.folder / "output" / "csvs"
        (csvs / "dark_numbers_r__train.csv").write_text(CALCULATIONS, encoding="utf-8")
        (csvs / "dark_numbers_r__train.json").write_text(json.dumps(record), encoding="utf-8")
        dark = client.get(f"/ui/results?run={s.run}&view=dark_numbers&export=xlsx")
        overview = client.get(f"/ui/results?run={s.run}&view=overview&export=csv")
        # A detail table longer than a page (500 rows at most per page).
        many = "".join(f"{i};{i};{i};a;b;0.5\n" for i in range(700))
        target = min(csvs.glob("misplaced_*.csv"), key=lambda f: len(f.name), default=None) \
            or csvs / "misplaced_r__train.csv"
        target.write_text(";id;Row;Model class;Class;Probability\n" + many, encoding="utf-8")
        page = client.get(f"/ui/results?run={s.run}&view=mispredictions").text
        allrows = client.get(f"/ui/results?run={s.run}&view=mispredictions&export=xlsx")
    sheets = load_workbook(io.BytesIO(dark.content)).sheetnames
    assert sheets[:3] == ["Inställningar", "Skattningar", "Beräkningar"]
    assert "Mörkertal" in dark.headers["content-disposition"].encode("latin-1").decode("utf-8") \
        or "rkertal" in dark.headers["content-disposition"]
    assert overview.content.decode("utf-8-sig").startswith("Utvärdering på testdata")
    book = load_workbook(io.BytesIO(allrows.content))
    assert book["Felklassificeringar"].max_row == 701                 # header + every row
    assert "700" in page or "Föregående" in page or "Nästa" in page   # the page shows less


def test_the_guides():
    sv = " ".join((ROOT / "docs" / "user_guide.sv.md").read_text(encoding="utf-8").split())
    assert "har knappen **Exportera** under tabellerna, till höger." in sv          # 301s
