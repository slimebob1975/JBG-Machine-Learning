"""301v (asked 2026-11-27), one sweep:
- the final model's pipeline with its tuned parameters is saved with a run's
  results, and result exports show it (runs before 301v say it is not recorded);
- the fake-data specification merges values on fewer than 5 rows too;
- a configuration can be copied to another project of the same source;
- housekeeping: the BACKLOG's ticked items moved out, version 0.20.2."""
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from JBGPipelineDescription import describe, summary, write

ROOT = Path(__file__).resolve().parent.parent


def test_the_pipeline_is_described_and_saved(tmp_path):
    model = Pipeline([("STA", StandardScaler()), ("LRN", LogisticRegression(C=0.25, max_iter=3000))])
    steps = describe(model)
    assert [s["class"] for s in steps] == ["StandardScaler", "LogisticRegression"]
    assert steps[1]["params"]["C"] == 0.25 and steps[1]["params"]["max_iter"] == 3000
    assert summary(steps).startswith("StandardScaler · LogisticRegression(C=0.25")
    config = SimpleNamespace(get_output_filepath=lambda kind: tmp_path / "output" / "csvs" /
                             f"{kind}_x.json")
    path = write(config, model)
    assert path.name == "final_pipeline_x.json"
    assert json.loads(path.read_text(encoding="utf-8"))["steps"] == steps
    from Config import Config
    assert Config().get_filename("final_pipeline").startswith("final_pipeline_")
    from sklearn.preprocessing import FunctionTransformer
    noisy = describe(Pipeline([("NOS", FunctionTransformer()), ("LRN", LogisticRegression())]))
    assert len(noisy) == 2 and summary(noisy).startswith("LogisticRegression(")   # NOS left out
    runner = (ROOT / "src" / "JBGTaskRunner.py").read_text(encoding="utf-8")
    assert runner.count("write_pipeline(") == 2                        # both model saves


def test_result_exports_show_the_final_pipeline(tmp_path):
    pytest.importorskip("fastapi")
    from openpyxl import load_workbook
    from test_revision_299b_csv_reclassification import _client, _setting
    with _client(tmp_path) as client:
        s = _setting(client, tmp_path)
        csvs = s.folder / "output" / "csvs"
        before = client.get(f"/ui/results?run={s.run}&view=overview&export=xlsx")
        model = Pipeline([("STA", StandardScaler()), ("LRN", LogisticRegression(C=0.25))])
        (csvs / "final_pipeline_r__train.json").write_text(
            json.dumps({"version": 1, "steps": describe(model)}), encoding="utf-8")
        after = client.get(f"/ui/results?run={s.run}&view=overview&export=xlsx")
    old = load_workbook(io.BytesIO(before.content))
    info = {r[0].value: r[1].value for r in old["Information"].iter_rows()}
    assert info["Slutlig pipeline"] == "inte sparad (körningar före 301v)"
    assert "Pipeline" not in old.sheetnames
    new = load_workbook(io.BytesIO(after.content))
    info = {r[0].value: r[1].value for r in new["Information"].iter_rows()}
    assert info["Slutlig pipeline"].startswith("StandardScaler · LogisticRegression(C=0.25")
    assert new.sheetnames[:2] == ["Information", "Pipeline"]
    rows = [[c.value for c in r] for r in new["Pipeline"].iter_rows()]
    assert rows[0] == ["Körning", "Steg", "Klass", "Parameter", "Värde"]
    assert ["", "LRN", "LogisticRegression", "C", 0.25] in rows or \
        [None, "LRN", "LogisticRegression", "C", 0.25] in rows


def test_the_specification_merges_values_on_fewer_than_five_rows():
    from JBGFakeDataSpec import OTHER, RARE_MIN_ROWS, build_spec
    frame = pd.DataFrame({"c": ["a"] * 290 + ["b"] * 6 + ["c"] * 4})    # 300 rows: 0.1 % = 0.3
    spec = build_spec(frame, roles={"c": "categorical"}, class_column=None, dataset_name="D",
                      source="csv", rows_total=300)
    values = {v["value"] for v in spec["columns"][0]["values"]}
    assert RARE_MIN_ROWS == 5 and spec["rare_min_rows"] == 5
    assert values == {"a", "b", OTHER}                                # "c" (4 rows) merged


def test_a_configuration_is_copied_to_another_project(tmp_path):
    pytest.importorskip("fastapi")
    from test_revision_288a_project_runs import _client, _setup
    with _client(tmp_path) as client:
        a, dataset, configuration = _setup(client)
        client.put(f"/api/projects/{a}/configurations/{configuration}",
                   json={"settings": {"debug": {"data_limit": 7}}, "expected_version": 0})
        b = client.post("/api/projects", json={"name": "Andra", "source": "csv"}).json()["project_id"]
        sql = client.post("/api/projects", json={"name": "SQL", "source": "sql"}).json()["project_id"]
        client.post(f"/ui/projects/{a}/open")
        page = client.get(f"/ui/configuration?configuration={configuration}").text
        done = client.post(f"/ui/configuration/{configuration}/copy",
                           data={"target_project_id": b, "name": "Standard"}, follow_redirects=False)
        again = client.post(f"/ui/configuration/{configuration}/copy",
                            data={"target_project_id": b, "name": "Standard"}, follow_redirects=False)
        to_sql = client.post(f"/api/projects/{a}/configurations/{configuration}/copy",
                             json={"target_project_id": sql, "name": "X"})
        listed = client.get(f"/api/projects/{b}/configurations").json()
        listed = listed if isinstance(listed, list) else listed.get("items", [])
        copied = client.get(f"/api/projects/{b}/configurations/{listed[0]['configuration_id']}").json()
    panel = page[page.index('class="panel copy"'):]
    panel = panel[:panel.index("</form>")]
    assert "Kopiera till ett annat projekt" in panel and "Andra" in panel and ">SQL<" not in panel
    assert "message=copied" in done.headers["location"]
    assert "message=copy_duplicate" in again.headers["location"]
    assert to_sql.status_code == 422
    assert copied["version"] == 0 and copied["settings"]["debug"]["data_limit"] == 7


def test_housekeeping_and_version():
    from JBGVersion import APP_VERSION
    assert APP_VERSION == "0.20.2"
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert changelog.startswith("## Version 0.20.2")
    backlog = (ROOT / "BACKLOG.md").read_text(encoding="utf-8").split("## Standing rules")[0]
    assert "Ticked items of revisions 300r to 301u were moved out" in backlog
    assert "Postponed 2026-11-27: a fake-data generator" in backlog
    assert "- [x] 301v: copy a configuration to another project" in backlog
