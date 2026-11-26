"""301d (asked 2026-11-24): the Dataset tab's Visualisation view, a 2D picture
of a sample of the dataset. Decided 2026-11-24: drawn in the browser with the
row's values on hover; numeric and categorical columns only; the sample random
with the same share of each class by default, or random, or the first rows."""
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from JBGDatasetVisualisation import (MDS_MAX, SAMPLE_MAX, VisualisationRefused, check_settings,
                                     draw_sample, prepare, visualise)

ROOT = Path(__file__).resolve().parent.parent


def _frame(n=400, seed=0):
    rng = np.random.default_rng(seed)
    return pd.DataFrame({"id": range(n), "k": rng.choice(["a", "b"], n, p=[0.8, 0.2]),
                         "n1": rng.normal(size=n), "n2": rng.normal(size=n) * 10,
                         "c1": rng.choice(["x", "y", "z"], n)})


# --- The sample --------------------------------------------------------------------------

def test_the_three_ways_to_draw_the_sample():
    frame = _frame(1000)
    share = (frame["k"] == "b").mean()
    stratified = draw_sample(frame, 200, "stratified", "k")
    assert len(stratified) == 200
    assert (stratified["k"] == "b").mean() == pytest.approx(share, abs=0.01)
    assert len(draw_sample(frame, 200, "random", "k")) == 200
    assert draw_sample(frame, 200, "first", "k")["id"].tolist() == list(range(200))
    assert len(draw_sample(frame, 5000, "stratified", "k")) == 1000            # all rows
    again = draw_sample(frame, 200, "stratified", "k")
    pd.testing.assert_frame_equal(stratified, again)                          # a fixed seed


def test_rows_without_a_class_are_sampled_as_a_group_of_their_own():
    frame = _frame(1000)
    frame.loc[:99, "k"] = None
    sample = draw_sample(frame, 100, "stratified", "k")
    assert sample["k"].isna().sum() == 10


# --- The computation ---------------------------------------------------------------------

def test_numeric_columns_are_standardised_and_categorical_one_hot():
    frame = _frame(50)
    frame.loc[3, "n1"] = None
    X = prepare(frame, ["n1", "n2"], ["c1"])
    assert X.shape == (50, 2 + 3)
    assert np.allclose(X[:, :2].mean(axis=0), 0, atol=1e-9)
    assert set(np.unique(X[:, 2:])) <= {0.0, 1.0} and (X[:, 2:].sum(axis=1) == 1).all()
    with pytest.raises(VisualisationRefused):
        prepare(frame, [], [])


@pytest.mark.parametrize("method", ["pca", "tsne", "mds"])
def test_each_method_gives_points_with_classes_clusters_and_values(method):
    frame = _frame(120)
    frame.loc[0, "k"] = None
    picture = visualise(frame, id_column="id", class_column="k", numeric=["n1", "n2"],
                        categorical=["c1"], method=method, clusters=3)
    assert picture["rows"] == len(picture["points"]) == 120
    assert picture["classes"] == ["a", "b"] and picture["unclassified"] == 1
    assert picture["clusters"] == 3 and {p["cluster"] for p in picture["points"]} == {0, 1, 2}
    assert picture["hover_columns"] == ["id", "k", "n1", "n2", "c1"]
    assert picture["points"][0]["class"] is None and picture["points"][0]["values"][0] == "0"
    assert (picture["explained"] is not None) == (method == "pca")
    again = visualise(frame, id_column="id", class_column="k", numeric=["n1", "n2"],
                      categorical=["c1"], method=method, clusters=3)
    assert again["points"] == picture["points"]                               # the same picture


def test_the_clusters_do_not_depend_on_the_method():
    frame = _frame(150)
    found = [[p["cluster"] for p in visualise(frame, id_column="id", class_column="k",
                                               numeric=["n1", "n2"], categorical=["c1"],
                                               method=m, clusters=4)["points"]]
             for m in ("pca", "tsne")]
    assert found[0] == found[1]


def test_without_clusters_or_class():
    picture = visualise(_frame(60), id_column=None, class_column=None, numeric=["n1"],
                        categorical=[], method="pca", clusters=0)
    assert picture["clusters"] == 0 and picture["classes"] == []
    assert all(p["cluster"] is None and p["class"] is None for p in picture["points"])


def test_the_settings_are_checked():
    check_settings("pca", 3, 1000, "stratified")
    for bad in (("umap", 3, 1000, "random"), ("pca", 9, 1000, "random"), ("pca", 3, 50, "random"),
                ("pca", 3, SAMPLE_MAX + 1, "random"), ("pca", 3, 1000, "every"),
                ("mds", 3, MDS_MAX + 100, "random")):
        with pytest.raises(VisualisationRefused):
            check_settings(*bad)


# --- SQL sampling ------------------------------------------------------------------------

def test_the_sql_queries():
    from JBGDatasetInspection import _sql_sample
    asked = []

    class Facts:
        _catalog, _table, rows = "Cat", "dbo.T", 10000

        def _query(self, sql):
            asked.append(sql)
            return [(1, "a", 0.5), (2, "b", 1.5)]
    for sampling in ("first", "random", "stratified"):
        frame = _sql_sample(Facts(), ["id", "k", "n1"], 1000, sampling, "k")
        assert list(frame.columns) == ["id", "k", "n1"] and len(frame) == 2
    first, random, stratified = asked
    assert first.startswith("SELECT TOP(1000) [id], [k], [n1] FROM [Cat].[dbo].[T]")
    assert random.endswith("ORDER BY NEWID()")
    assert "ROW_NUMBER() OVER (PARTITION BY [k] ORDER BY NEWID())" in stratified
    assert "CEILING(jbg_count * 0.10000000)" in stratified


# --- The route and the page --------------------------------------------------------------

def test_the_route_and_the_page(tmp_path):
    pytest.importorskip("fastapi")
    from test_revision_288a_project_runs import _client, _setup
    from test_revision_301a_share_sliders import IMBALANCED
    with _client(tmp_path) as client:
        project, dataset, _ = _setup(client, data=IMBALANCED)
        base = f"/api/projects/{project}/datasets/{dataset}/visualisation"
        drawn = client.get(base, params={"method": "tsne", "clusters": 2, "sample_size": 100})
        cached = client.get(base, params={"method": "tsne", "clusters": 2, "sample_size": 100})
        refused = client.get(base, params={"method": "mds", "sample_size": 2500})
        bare = client.post(f"/api/projects/{project}/datasets/csv", data={
            "name": "Utan roller", "role": "training"},
            files={"file": ("t.csv", IMBALANCED, "text/csv")}).json()["dataset_id"]
        no_roles = client.get(f"/api/projects/{project}/datasets/{bare}/visualisation")
        client.post(f"/ui/projects/{project}/open")
        page = client.get(f"/ui/dataset?dataset={dataset}&view=visualisation").text
    assert drawn.status_code == 200 and drawn.json()["rows"] == 20
    assert drawn.json()["classes"] == ["a", "b"] and drawn.json()["clusters"] == 2
    assert cached.json() == drawn.json()
    assert refused.status_code == 422 and refused.json()["detail"] == "mds_sample_size"
    assert no_roles.status_code == 422 and no_roles.json()["detail"] == "roles"
    assert ">Visualisering</a>" in page and "data-viz-form" in page
    assert f'data-url="/api/projects/{project}/datasets/{dataset}/visualisation"' in page
    assert "Slumpvis, samma andel av varje klass" in page and "Kluster (K-means)" in page
    assert 'data-reason-roles="Ange kolumnrollerna först.' in page


def test_the_script_and_the_guides():
    script = (ROOT / "src" / "web" / "static" / "jbg.js").read_text(encoding="utf-8")
    assert 'querySelectorAll("form[data-viz-form]").forEach(wireVisualisation)' in script
    assert "row.insertCell().textContent = point.values[j];" in script        # values as text
    sv = (ROOT / "docs" / "user_guide.sv.md").read_text(encoding="utf-8")
    en = (ROOT / "docs" / "user_guide.en.md").read_text(encoding="utf-8")
    assert "**Visualisering** ritar ett urval" in sv and "**Visualisation** draws a sample" in en
