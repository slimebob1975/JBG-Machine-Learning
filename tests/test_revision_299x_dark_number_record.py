"""299x (agreed 2026-11-16, DN-01 result format): every Dark Numbers computation
writes a JSON result record next to the CSV files (unchanged): schema version,
method and version, the parameters used, and one entry per estimate (v1.2:
estimand D_JBG, no interval, status ok/capped/undefined). Results -> Dark
Numbers shows the equation with the method version and the settings used only
for runs with a record; older runs get a note. The result table uses the full
width."""
import json
from types import SimpleNamespace

import pandas as pd

from JBGDarkNumberRecord import SCHEMA_VERSION, build, read, record_path, write
from test_revision_299b_csv_reclassification import _client, _setting

FRAME = pd.DataFrame([
    {"Model type": "D_cv_test - Cross", "type": "separated_alpha", "target": "a", "corr": 1.0,
     "corr_source": "not applied (test part)", "dark_number": 0.02, "capped": False},
    {"Model type": "", "type": "separated_alpha", "target": "b", "corr": 1.0,
     "corr_source": "not applied (test part)", "dark_number": 1.0, "capped": True},
    {"Model type": "D_retrained_full - Final", "type": "separated_alpha", "target": "a",
     "corr": -1.0, "corr_source": "undefined/out_of_bounds (direct)", "dark_number": -1.0,
     "capped": False},
    {"Model type": "Combined (legacy full-data)", "type": "separated_alpha", "target": "a",
     "corr": 2.0, "corr_source": "direct", "dark_number": -1.0, "capped": False},
])
CONFIG = SimpleNamespace(
    mode=SimpleNamespace(dark_number_method=SimpleNamespace(name="LINEAR"),
                         dark_number_alpha=SimpleNamespace(name="SEPARATED"),
                         dark_number_flip_fraction=0.2),
    get_dark_number_calculation_type=lambda: "separated_alpha",
    get_dark_number_target=lambda: "")


def test_the_record():
    record = build(CONFIG, FRAME, {"flip_fraction": None, "random_state": 42, "root_degree": 3})
    assert record["schema_version"] == SCHEMA_VERSION == 1
    assert record["method"] == {"name": "JBG", "version": "1.3"}      # 300l
    p = record["parameters"]
    assert (p["calculation_type"], p["method"], p["alpha"], p["flip_fraction"]) == \
        ("separated_alpha", "LINEAR", "SEPARATED", 0.2)
    assert (p["flip_test_folds"], p["flip_test_repeats"], p["correction_max"], p["cap"],
            p["memorisation_fit"], p["memorisation_gap"], p["random_state"], p["root_degree"]) == \
        (4, 2, 20.0, 1.0, 0.95, 0.05, 42, 3)                           # 300v: was 10
    entries = record["estimates"]
    assert [(e["scope"], e["target"], e["status"], e["value"]) for e in entries] == [
        ("D_cv_test", "a", "ok", 0.02), ("D_cv_test", "b", "capped", 1.0),
        ("D_re_full", "a", "undefined", None), ("D_comb", "a", "undefined", None)]
    assert [e["reason"] for e in entries[2:]] == ["undefined correction", "undefined rate"]
    assert all(e["estimand"] == "D_JBG" and e["interval"] is None for e in entries)


def test_written_beside_the_csv_and_read_back(tmp_path):
    csvs = tmp_path / "output" / "csvs"
    csvs.mkdir(parents=True)
    path = write(CONFIG, FRAME, {"random_state": 7}, csvs / "dark_numbers_r__train.csv")
    assert path == record_path(csvs / "dark_numbers_r__train.csv") == csvs / "dark_numbers_r__train.json"
    (csvs / "dark_numbers_conf_matrix_r__train.json").write_text("{}", encoding="utf-8")
    assert read(csvs)["parameters"]["random_state"] == 7
    path.write_text("{broken", encoding="utf-8")
    assert read(csvs) is None and read(tmp_path / "missing") is None


CALCULATIONS = (";Model type;type;target;alphas;corr;corr_model;corr_source;dark_number\n"
                "0;D_cv_test - Cross-trained model;separated_alpha;a;[0.5, 0.5];1,0;Cross-trained model;not applied (test part);0,01432\n"
                "0;D_cv_full - Cross-trained model;separated_alpha;a;[0.5, 0.5];2,0;Cross-trained model;direct;0,004082\n")


def test_the_results_tab_with_and_without_a_record(tmp_path):
    with _client(tmp_path) as client:
        s = _setting(client, tmp_path)
        csvs = s.folder / "output" / "csvs"
        (csvs / "dark_numbers_r__train.csv").write_text(CALCULATIONS, encoding="utf-8")
        page = client.get(f"/ui/results?run={s.run}&view=dark_numbers").text
        assert "Beräknat med en tidigare version av metoden (före 1.2)" in page
        assert "Ekvationen" not in page
        record = build(CONFIG, pd.DataFrame(), {"random_state": 42})
        (csvs / "dark_numbers_r__train.json").write_text(json.dumps(record), encoding="utf-8")
        page = client.get(f"/ui/results?run={s.run}&view=dark_numbers").text
    assert "Ekvationen <span class=\"muted\">· JBG 1.3</span>" in page
    assert "Inställningar som användes: ommärkningsandel 0,2 · ommärkningstest 4 × 2" in page
    assert "tidigare version" not in page


def test_the_table_uses_the_full_width():
    from JBGWebUI import WEB
    css = (WEB / "static" / "jbg.css").read_text(encoding="utf-8")
    assert ".dark-range { width: 100%; max-width: none; }" in css
    assert ".dark-counts { min-width: 340px; }" in css
