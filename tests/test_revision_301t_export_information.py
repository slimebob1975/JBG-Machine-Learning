"""301t (asked 2026-11-27):
- the Profile view's JSON specification button stands bottom left, on the row
  of the Export button, and its explanation is in the guide (About);
- every export names the dataset used, in the file name and in a first
  Information table (also first in CSV);
- exports of results also name the run, its configuration and the pipeline
  (the model comparison's best row)."""
import io
import json
from pathlib import Path
from urllib.parse import unquote

import pandas as pd
import pytest

pytest.importorskip("fastapi")

ROOT = Path(__file__).resolve().parent.parent


def _name(response):
    return unquote(response.headers["content-disposition"].split("filename*=UTF-8''")[1])


def _information(response):
    from openpyxl import load_workbook
    book = load_workbook(io.BytesIO(response.content))
    assert book.sheetnames[0] == "Information"
    return {row[0].value: [c.value for c in row[1:]] for row in book["Information"].iter_rows()}, book


def test_the_specification_button_is_on_the_export_row(tmp_path):
    from test_revision_288a_project_runs import _client, _setup
    with _client(tmp_path) as client:
        project, dataset, _ = _setup(client)
        client.post(f"/ui/projects/{project}/open")
        page = client.get(f"/ui/dataset?dataset={dataset}&view=profile").text
    row = page[page.index('class="export-links"'):]
    row = row[:row.index("</p>")]
    assert row.index('class="btn sub left"') < row.index("Exportera (")
    assert f"/ui/dataset/{dataset}/fake-data-spec" in row
    assert "Inga riktiga rader" not in page                       # the explanation is in About


def test_every_export_names_the_dataset(tmp_path):
    from test_revision_288a_project_runs import _client
    from test_revision_301c_run_history import _two_versions
    with _client(tmp_path) as client:
        project, dataset, configuration, first, second = _two_versions(client)
        profile = client.get(f"/ui/dataset?dataset={dataset}&view=profile&export=xlsx")
        settings = client.get(f"/ui/configuration?configuration={configuration}&export=xlsx")
        compare = client.get(f"/ui/history?compare={first}&compare={second}&export=xlsx")
        csv = client.get(f"/ui/history?run={first}&export=csv")
    info, _ = _information(profile)
    assert info["Dataset"] == ["Data"] and _name(profile).startswith("Dataset Data Profil ")
    info, _ = _information(settings)
    assert info["Aktivt träningsdataset"] == ["Data"] and " - Data " in _name(settings)
    info, book = _information(compare)
    assert info["Om exporten"] == ["Körning 1", "Körning 2"]
    assert info["Dataset"] == ["Data", "Data"]
    assert info["Konfiguration"] == ["Standard v0", "Standard v1"]
    assert "Vinnande pipeline" in info and info["Körning"] == [first, second]
    assert csv.content.decode("utf-8-sig").splitlines()[:2] == ["Information", "Om exporten;Värde"]
    assert " - Data " in _name(csv)


def test_results_name_the_pipeline(tmp_path):
    from JBGDarkNumberRecord import build
    from test_revision_299b_csv_reclassification import _client, _setting
    from test_revision_299x_dark_number_record import CALCULATIONS, CONFIG
    record = build(CONFIG, pd.DataFrame(), {"random_state": 42})
    with _client(tmp_path) as client:
        s = _setting(client, tmp_path)
        csvs = s.folder / "output" / "csvs"
        (csvs / "dark_numbers_r__train.csv").write_text(CALCULATIONS, encoding="utf-8")
        (csvs / "dark_numbers_r__train.json").write_text(json.dumps(record), encoding="utf-8")
        (csvs / "crossval_r__train.csv").write_text(
            ";Oversampling;Undersampling;Preprocessor;Feature Reduction;Algorithm (Library);"
            "Mean cv;Stdev.;Exception\n0;SME;NUG;STA;NOR;LRN - Logistic Regression;0,91;0,02;\n",
            encoding="utf-8")
        dark = client.get(f"/ui/results?run={s.run}&view=dark_numbers&export=xlsx")
    info, book = _information(dark)
    assert info["Vinnande pipeline"] == ["SME · STA · LRN - Logistic Regression"]
    assert info["Dataset"][0] and info["Körning"] == [s.run]
    assert book.sheetnames[1] == "Inställningar"


def test_the_guide_explains_the_specification():
    sv = " ".join((ROOT / "docs" / "user_guide.sv.md").read_text(encoding="utf-8").split())
    assert "**Exportera specifikation för fejkdata (JSON)**" in sv
