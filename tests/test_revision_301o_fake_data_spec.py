"""301o (asked 2026-11-26): the Profile view exports a JSON specification for
generating fake data: distributions per column and per class, and correlations
between the numeric columns, without any real row. Values under 0.1 % of the
rows are merged into Övrigt, numbers are quantiles from 0.1 to 99.9 %, free
text only lengths (decided 2026-11-26)."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from JBGFakeDataSpec import OTHER, QUANTILES, RARE_SHARE, build_spec

ROOT = Path(__file__).resolve().parent.parent


def _frame(n=5000, seed=0):
    rng = np.random.default_rng(seed)
    k = rng.choice(["a", "b"], n, p=[0.8, 0.2])
    x = rng.normal(size=n) + (k == "b") * 2
    frame = pd.DataFrame({"id": range(n), "k": k, "x": x, "y": x * 2 + rng.normal(size=n) * 0.1,
                          "c": rng.choice(["p", "q", "r"], n),
                          "namn": [f"Person {i}" for i in range(n)],
                          "d": pd.date_range("2025-01-01", periods=n, freq="h").astype(str)})
    frame.loc[0, "c"] = "unik"                       # once in 5000 rows: under 0.1 %
    frame.loc[:99, "x"] = None                       # 2 % missing
    return frame


ROLES = {"id": "id", "k": "class", "x": "numeric", "y": "numeric", "c": "categorical",
         "namn": "text", "d": "date"}


def test_the_specification():
    spec = build_spec(_frame(), roles=ROLES, class_column="k", dataset_name="D", source="csv",
                      rows_total=5000)
    assert (spec["schema"], spec["version"], spec["rare_share"]) == ("jbg-fake-data-spec", 1, RARE_SHARE)
    assert spec["rows_used"] == spec["rows"] == 5000 and spec["sampled"] is False
    assert [c["value"] for c in spec["classes"]] == ["a", "b"]
    by = {c["name"]: c for c in spec["columns"]}
    assert by["id"]["type"] == "id" and "note" in by["id"] and "quantiles" not in by["id"]
    assert by["x"]["missing_share"] == pytest.approx(0.02)
    assert list(by["x"]["quantiles"]) == [f"{q:g}" for q in QUANTILES]
    assert by["x"]["by_class"]["b"]["mean"] > by["x"]["by_class"]["a"]["mean"] + 1.5   # differs
    values = {v["value"]: v["share"] for v in by["c"]["values"]}
    assert "unik" not in values and OTHER in values and by["c"]["merged_values"] == 1
    assert by["d"]["quantiles"]["0.5"].startswith("2025-")
    assert by["namn"]["type"] == "text" and set(by["namn"]) >= {"length", "words", "distinct_share"}
    dumped = json.dumps(spec, ensure_ascii=False)
    assert "Person 1" not in dumped and "unik" not in dumped               # no real values
    corr = spec["correlations"]
    assert corr["columns"] == ["x", "y"] and corr["matrix"][0][1] > 0.99


def test_types_are_inferred_without_roles():
    spec = build_spec(_frame(400), roles={}, class_column=None, dataset_name="D", source="sql",
                      rows_total=10_000)
    by = {c["name"]: c["type"] for c in spec["columns"]}
    assert by["x"] == "numeric" and by["c"] == "categorical" and by["namn"] == "text"
    assert spec["sampled"] is True and spec["classes"] is None


def test_the_download_from_the_profile_view(tmp_path):
    pytest.importorskip("fastapi")
    from test_revision_288a_project_runs import _client
    data = ("id;namn;n1;k\r\n" + "".join(f"{i};Namn {i};{i % 7}.5;{'a' if i % 3 else 'b'}\r\n"
                                         for i in range(1, 41))).encode("utf-8")
    with _client(tmp_path) as client:
        project = client.post("/api/projects", json={"name": "P", "source": "csv"}).json()["project_id"]
        client.post(f"/ui/projects/{project}/open")
        dataset = client.post(f"/api/projects/{project}/datasets/csv",
                              data={"name": "Data", "role": "training"},
                              files={"file": ("d.csv", data, "text/csv")}).json()["dataset_id"]
        client.put(f"/api/projects/{project}/datasets/{dataset}/roles", json={"columns": {
            "id": "id", "namn": "text", "n1": "numeric", "k": "class"}})
        page = client.get(f"/ui/dataset?dataset={dataset}&view=profile").text
        download = client.get(f"/ui/dataset/{dataset}/fake-data-spec")
        api = client.get(f"/api/projects/{project}/datasets/{dataset}/fake-data-spec")
    assert "Exportera specifikation för fejkdata (JSON)" in page
    assert f'href="/ui/dataset/{dataset}/fake-data-spec"' in page
    assert download.status_code == 200 and download.headers["content-type"] == "application/json"
    assert "specifikation.json" in download.headers["content-disposition"]
    spec = json.loads(download.content)
    assert spec["dataset"] == "Data" and spec["class_column"] == "k" and spec["rows"] == 40
    assert "Namn 1" not in download.text
    assert api.json()["schema"] == "jbg-fake-data-spec"


def test_the_guides():
    sv = " ".join((ROOT / "docs" / "user_guide.sv.md").read_text(encoding="utf-8").split())
    assert "**Exportera specifikation för fejkdata (JSON)**" in sv
