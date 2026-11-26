"""301j (asked 2026-11-26): the dataset picture shows free-text and date columns
on hover (not used in the computation), remembers its settings per dataset
when the view is left, and starts the point size in the middle of its range."""
from pathlib import Path

import pandas as pd

from JBGDatasetVisualisation import HOVER_COLUMNS, visualise

ROOT = Path(__file__).resolve().parent.parent


def test_free_text_shows_on_hover_but_is_not_computed():
    frame = pd.DataFrame({"id": range(40), "k": ["a", "b"] * 20,
                          "beskrivning": [f"System {i}" for i in range(40)],
                          **{f"c{i}": [str(j % 3) for j in range(40)] for i in range(15)}})
    picture = visualise(frame, id_column="id", class_column="k", numeric=[],
                        categorical=[f"c{i}" for i in range(15)], method="pca", clusters=0,
                        shown=["beskrivning"])
    assert picture["hover_columns"][:3] == ["id", "k", "beskrivning"]
    assert len(picture["hover_columns"]) == HOVER_COLUMNS
    assert "beskrivning" not in picture["features"]["categorical"]
    assert picture["points"][5]["values"][2] == "System 5"


def test_the_service_reads_text_columns_for_hover(tmp_path):
    import pytest
    pytest.importorskip("fastapi")
    from test_revision_288a_project_runs import _client
    data = ("id;namn;n1;k\r\n" + "".join(f"{i};Namn {i};{i % 7}.5;{'a' if i % 3 else 'b'}\r\n"
                                         for i in range(1, 41))).encode("utf-8")
    with _client(tmp_path) as client:
        project = client.post("/api/projects", json={"name": "P", "source": "csv"}).json()["project_id"]
        dataset = client.post(f"/api/projects/{project}/datasets/csv",
                              data={"name": "D", "role": "training"},
                              files={"file": ("d.csv", data, "text/csv")}).json()["dataset_id"]
        base = f"/api/projects/{project}/datasets/{dataset}"
        client.put(base + "/roles", json={"columns": {"id": "id", "namn": "text", "n1": "numeric",
                                                      "k": "class"}})
        picture = client.get(base + "/visualisation", params={"sample_size": 100,
                                                               "sampling": "first"}).json()
    assert picture["hover_columns"] == ["id", "k", "namn", "n1"]
    assert picture["features"] == {"numeric": ["n1"], "categorical": []}
    assert picture["points"][0]["values"][2] == "Namn 1"


def test_the_picture_is_remembered_and_the_size_centred():
    script = (ROOT / "src" / "web" / "static" / "jbg.js").read_text(encoding="utf-8")
    assert 'var memory = "jbg-viz:" + form.getAttribute("data-url");' in script
    assert "window.localStorage.setItem(memory, JSON.stringify(settings));" in script
    assert 'form.dispatchEvent(new Event("submit", { cancelable: true }));' in script
    page = (ROOT / "src" / "web" / "templates" / "dataset.html").read_text(encoding="utf-8")
    assert 'min="1" max="10" step="0.5" value="5.5" data-viz-size' in page
    assert (1 + 10) / 2 == 5.5


def test_the_guides():
    sv = " ".join((ROOT / "docs" / "user_guide.sv.md").read_text(encoding="utf-8").split())
    assert "även fritext- och datumkolumner som inte används i beräkningen" in sv
    assert "Bilden och dess inställningar finns kvar när du byter vy" in sv
