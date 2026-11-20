"""300l, JBG 1.3 (decided 2026-11-19): c is the correction factor for
overtraining, c_in / c_unseen = r_unseen / r_in from the flip test's parts.
Runs saved with an earlier version show their values as saved, with a note."""
import json

import pandas as pd

from JBGDarkNumberRecord import build
from JBGDarkNumbers import DarkNumberCalculator
from test_revision_299b_csv_reclassification import _client, _setting
from test_revision_299x_dark_number_record import CALCULATIONS, CONFIG


def test_the_version():
    assert DarkNumberCalculator.METHOD_VERSION == "1.3"


def test_an_earlier_versions_run_gets_a_note(tmp_path):
    record = build(CONFIG, pd.DataFrame(), {"random_state": 42})
    record["method"]["version"] = "1.2"
    with _client(tmp_path) as client:
        s = _setting(client, tmp_path)
        csvs = s.folder / "output" / "csvs"
        (csvs / "dark_numbers_r__train.csv").write_text(CALCULATIONS, encoding="utf-8")
        (csvs / "dark_numbers_r__train.json").write_text(json.dumps(record), encoding="utf-8")
        old = client.get(f"/ui/results?run={s.run}&view=dark_numbers").text
        record["method"]["version"] = "1.3"
        (csvs / "dark_numbers_r__train.json").write_text(json.dumps(record), encoding="utf-8")
        new = client.get(f"/ui/results?run={s.run}&view=dark_numbers").text
    assert "· JBG 1.2" in old and "Beräknat med en tidigare version av metoden. Värdena" in old
    assert "· JBG 1.3" in new and "Beräknat med en tidigare version av metoden. Värdena" not in new


def test_the_explanation_of_c():
    from JBGWebUI import _load_catalog
    from JBGWebUIResults import EQUATION_PARTS
    text = dict((s, t) for s, t, _ in EQUATION_PARTS)["c"]
    assert "c = c in the training rows / c in the unseen part" in text
    assert "korrektionsfaktorn för överträning" in _load_catalog("sv")[text].lower()
