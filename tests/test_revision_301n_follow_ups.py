"""301n (2026-11-26): follow-ups and housekeeping after 0.20.1.
- A prediction CSV gets JBG_RadId at upload when the training dataset's ID
  column is JBG_RadId (301i) and the file lacks it.
- Run History lists up to 1000 runs (was 200) and says when there are more
  (decided 2026-11-26).
- Kept Excel workbooks older than a day are removed for every user at start.
- The 295c test works on a copy of sv.po; the BACKLOG's ticked items moved out."""
import os
import time
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from test_revision_288a_project_runs import _client  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TRAIN = ("System;Område;Risknivå\r\n" + "".join(
    f"System {i % 5};Område {i % 3};{'Hög' if i % 4 == 0 else 'Låg'}\r\n" for i in range(1, 21))
         ).encode("cp1252")
PREDICT = ("System;Område\r\n" + "".join(
    f"System {i % 5};Område {i % 3}\r\n" for i in range(1, 8))).encode("cp1252")


def _trained_with_radid(client):
    project = client.post("/api/projects", json={"name": "P", "source": "csv"}).json()["project_id"]
    client.post(f"/ui/projects/{project}/open")
    dataset = client.post(f"/api/projects/{project}/datasets/csv",
                          data={"name": "Träning", "role": "training"},
                          files={"file": ("t.csv", TRAIN, "text/csv")}).json()["dataset_id"]
    base = f"/api/projects/{project}/datasets/{dataset}"
    client.post(base + "/id-column")
    client.put(base + "/roles", json={"columns": {"JBG_RadId": "id", "System": "categorical",
                                                  "Område": "categorical", "Risknivå": "class"}})
    client.post(base + "/activate")
    return project


def test_a_prediction_file_gets_jbg_radid(tmp_path):
    with _client(tmp_path) as client:
        project = _trained_with_radid(client)
        api = client.post(f"/api/projects/{project}/datasets/csv",
                          data={"name": "Ny", "role": "prediction"},
                          files={"file": ("p.csv", PREDICT, "text/csv")})
        form = client.post("/ui/dataset/csv", data={"name": "Ny 2", "role": "prediction"},
                           files={"file": ("p.csv", PREDICT, "text/csv")}, follow_redirects=False)
        shown = client.get(form.headers["location"]).text
        dataset = api.json()["dataset_id"]
        content = client.get(f"/ui/dataset/{dataset}/download").content.decode("cp1252")
        mixed = client.post(f"/api/projects/{project}/datasets/csv",
                            data={"name": "Blandad", "role": "mixed"},
                            files={"file": ("m.csv", TRAIN, "text/csv")}).json()
    assert api.status_code == 201 and api.json()["upload"]["id_added"] is True
    assert api.json()["upload"]["columns"][0] == "JBG_RadId"
    assert content.splitlines()[:3] == ["JBG_RadId;System;Område", "1;System 1;Område 1",
                                        "2;System 2;Område 2"]
    assert "message=added_with_id" in form.headers["location"]
    assert "JBG_RadId lades till, numrerad från 1" in shown
    assert mixed["upload"]["id_added"] is False and mixed["upload"]["columns"][0] == "System"


def test_a_prediction_file_with_its_own_radid_is_kept(tmp_path):
    with _client(tmp_path) as client:
        project = _trained_with_radid(client)
        own = ("JBG_RadId;System;Område\r\n7;System 1;Område 1\r\n9;System 2;Område 2\r\n"
               ).encode("utf-8")
        response = client.post(f"/api/projects/{project}/datasets/csv",
                               data={"name": "Egen", "role": "prediction"},
                               files={"file": ("p.csv", own, "text/csv")}).json()
    assert response["upload"]["id_added"] is False and response["upload"]["rows"] == 2


def test_run_history_says_when_there_are_more(tmp_path, monkeypatch):
    import JBGWebUIHistory
    from test_revision_301c_run_history import _two_versions
    monkeypatch.setattr(JBGWebUIHistory, "HISTORY_LIMIT", 1)
    with _client(tmp_path) as client:
        _two_versions(client)
        page = client.get("/ui/history").text
    assert "Bara de senaste 1 körningarna i projektet visas." in page
    assert JBGWebUIHistory.HISTORY_LIMIT == 1


def test_the_limit_is_1000():
    import JBGWebUIHistory
    assert JBGWebUIHistory.HISTORY_LIMIT == 1000


def test_old_workbooks_are_swept_for_everyone(tmp_path):
    from types import SimpleNamespace
    from JBGDatasetService import DatasetService
    holder = SimpleNamespace(EXCEL_ROOT=tmp_path / "jbg_excel",
                             EXCEL_KEEP_SECONDS=DatasetService.EXCEL_KEEP_SECONDS)
    for user in ("a", "b"):
        folder = holder.EXCEL_ROOT / user
        folder.mkdir(parents=True)
        (folder / "old.xlsx").write_bytes(b"x")
        (folder / "new.xlsx").write_bytes(b"x")
        stale = time.time() - 2 * 24 * 3600
        os.utime(folder / "old.xlsx", (stale, stale))
    assert DatasetService.sweep_excel(holder) == 2
    assert sorted(p.name for p in holder.EXCEL_ROOT.rglob("*.xlsx")) == ["new.xlsx", "new.xlsx"]


def test_housekeeping():
    backlog = (ROOT / "BACKLOG.md").read_text(encoding="utf-8")
    head = backlog.split("## Standing rules")[0]
    import re
    # 301o: later revisions tick their own items; none of 300r to 301m is left.
    ticked = re.findall(r"^- \[x\] (30\d[a-z]|301[a-z])", head, flags=re.M)
    assert not [r for r in ticked if "300r" <= r <= "301m"]
    assert "- [x] 301n. Found with 301i" in head
    assert "Ticked items of revisions 300r to 301m were moved out in 301n" in head
    assert "Known limitation (301a)" in head
    deps = (ROOT / "docs" / "dependencies.md").read_text(encoding="utf-8")
    assert "## Version 0.20.1 (301m, 2026-11-26)" in deps
    test295c = (ROOT / "tests" / "test_revision_295c_predictions.py").read_text(encoding="utf-8")
    assert 'monkeypatch.setattr(JBGWebUI, "WEB", web)' in test295c
