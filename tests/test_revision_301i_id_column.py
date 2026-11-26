"""301i (asked 2026-11-26): a CSV dataset where no column can be the ID (filled
in and unique on every row) is told so at upload, and Column roles offers to
add one: JBG_RadId, numbered 1, 2, 3 ..., first in the file, written as a new
version of the file (decided 2026-11-26), offered only when no column can be
the ID. Also: API uploads detect the encoding too (301h covered the form only).
The test file is made up."""
import csv
import io
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from test_revision_288a_project_runs import _client  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
# No column is unique: every value repeats. One cell holds a quoted line break.
NO_ID = ("System;Område;Risknivå\r\n"
         + "".join(f"System {i % 5};Område {i % 3};{'Hög' if i % 4 == 0 else 'Låg'}\r\n"
                   for i in range(1, 21))
         + '"System\nmed radbrytning";Område 1;Låg\r\n').encode("cp1252")
WITH_ID = "Id;System;Risknivå\r\n1;A;Hög\r\n2;B;Låg\r\n3;C;Låg\r\n".encode("cp1252")


def _project(client, source="csv"):
    project = client.post("/api/projects", json={"name": "P", "source": source}).json()["project_id"]
    client.post(f"/ui/projects/{project}/open")
    return project


def _upload(client, project, data, name="Data"):
    return client.post("/ui/dataset/csv", data={"name": name, "role": "training"},
                       files={"file": ("d.csv", data, "text/csv")}, follow_redirects=False)


def test_the_upload_says_no_column_can_be_the_id(tmp_path):
    with _client(tmp_path) as client:
        project = _project(client)
        lacking = _upload(client, project, NO_ID)
        fine = _upload(client, project, WITH_ID, "Med ID")
        shown = client.get(lacking.headers["location"]).text
    assert "message=added_no_id" in lacking.headers["location"]
    assert "message=added" in fine.headers["location"] and "added_no_id" not in fine.headers["location"]
    assert "Ingen kolumn kan vara ID-kolumn (ifylld och unik på varje rad)" in shown


def test_column_roles_add_the_id_column(tmp_path):
    with _client(tmp_path) as client:
        project = _project(client)
        dataset = _upload(client, project, NO_ID).headers["location"].split("dataset=")[1].split("&")[0]
        before = client.get(f"/ui/dataset?dataset={dataset}&view=roles").text
        added = client.post(f"/ui/dataset/{dataset}/id-column", follow_redirects=False)
        after = client.get(added.headers["location"]).text
        content = client.get(f"/ui/dataset/{dataset}/download").content      # Hämta CSV
        again = client.post(f"/ui/dataset/{dataset}/id-column", follow_redirects=False)
    assert "Lägg till en ID-kolumn" in before
    assert f'action="/ui/dataset/{dataset}/id-column"' in before
    assert "message=id_added" in added.headers["location"]
    assert "ID-kolumnen JBG_RadId lades till" in after and "Lägg till en ID-kolumn" not in after
    rows = list(csv.reader(io.StringIO(content.decode("cp1252"), newline=""), delimiter=";"))
    assert rows[0] == ["JBG_RadId", "System", "Område", "Risknivå"]
    assert [r[0] for r in rows[1:]] == [str(i) for i in range(1, 22)]
    assert rows[-1][1] == "System\nmed radbrytning"                   # the quoted cell kept
    assert "message=id_exists" in again.headers["location"]


def test_the_api_adds_it_and_the_roles_save(tmp_path):
    with _client(tmp_path) as client:
        project = _project(client)
        upload = client.post(f"/api/projects/{project}/datasets/csv",
                             data={"name": "Data", "role": "training"},
                             files={"file": ("d.csv", NO_ID, "text/csv")})
        dataset = upload.json()["dataset_id"]
        base = f"/api/projects/{project}/datasets/{dataset}"
        refused = client.put(base + "/roles", json={"columns": {
            "System": "text", "Område": "categorical", "Risknivå": "class"}})
        added = client.post(base + "/id-column")
        saved = client.put(base + "/roles", json={"columns": {
            "JBG_RadId": "id", "System": "text", "Område": "categorical", "Risknivå": "class"}})
        valid = client.post(base + "/validate")
    assert upload.status_code == 201 and upload.json()["upload"]["encoding"] == "cp1252"   # 301h, API
    assert upload.json()["upload"]["id_candidates"] == []
    assert refused.status_code == 422
    assert added.status_code == 200 and added.json()["upload"]["id_candidates"] == ["JBG_RadId"]
    assert added.json()["upload"]["rows"] == 21 and added.json()["validation_state"] == "unverified"
    assert saved.status_code == 200 and valid.json()["validation_state"] == "valid"


def test_it_is_refused_where_it_is_not_needed(tmp_path):
    with _client(tmp_path) as client:
        project = _project(client)
        dataset = _upload(client, project, WITH_ID).headers["location"].split("dataset=")[1].split("&")[0]
        page = client.get(f"/ui/dataset?dataset={dataset}&view=roles").text
        refused = client.post(f"/api/projects/{project}/datasets/{dataset}/id-column")
        form = client.post(f"/ui/dataset/{dataset}/id-column", follow_redirects=False)
        sql = client.post("/api/projects", json={"name": "S", "source": "sql"}).json()["project_id"]
        no_sql = client.post(f"/api/projects/{sql}/datasets/{dataset}/id-column")
    assert "Lägg till en ID-kolumn" not in page
    assert refused.status_code == 422 and refused.json()["detail"] == "has_id_candidate"
    assert "message=id_not_needed" in form.headers["location"]
    assert no_sql.status_code in (404, 409, 422)


def test_the_guides():
    sv = " ".join((ROOT / "docs" / "user_guide.sv.md").read_text(encoding="utf-8").split())
    en = " ".join((ROOT / "docs" / "user_guide.en.md").read_text(encoding="utf-8").split())
    assert "Kolumnroller erbjuder **Lägg till en ID-kolumn**" in sv
    assert "Column roles offers **Add an ID column**" in en
