"""301g (asked 2026-11-24): the About tab's text fills its panel, and the
dataset picture marks outliers (Isolation Forest or Local Outlier Factor, a
choice in the form) and draws dashed lines between the K-means clusters
(agreed 2026-11-24), traced in the picture."""
from pathlib import Path

import numpy as np
import pytest

from JBGDatasetVisualisation import (VisualisationRefused, check_settings, cluster_boundaries,
                                     marked_outliers, outlier_scores, visualise)
from test_revision_301d_dataset_picture import _frame

ROOT = Path(__file__).resolve().parent.parent


def test_the_about_text_fills_the_panel():
    css = (ROOT / "src" / "web" / "static" / "jbg.css").read_text(encoding="utf-8")
    assert ".guide { max-width: none; }" in css and ".guide { max-width: 80ch; }" not in css


@pytest.mark.parametrize("method", ["iforest", "lof"])
def test_the_outliers_are_the_most_unusual_share(method):
    rng = np.random.default_rng(1)
    X = np.vstack([rng.normal(size=(196, 3)), [[9, 9, 9], [-9, 9, -9], [9, -9, 9], [-9, -9, -9]]])
    scores = outlier_scores(X, method)
    marked = marked_outliers(scores, 2.0)                        # 2 % of 200 = 4 rows
    assert marked.sum() == 4 and set(np.flatnonzero(marked)) == {196, 197, 198, 199}
    assert outlier_scores(X, "none") is None
    assert marked_outliers(scores, 0.1).sum() == 1               # at least one


def test_the_lines_lie_between_the_clusters():
    rng = np.random.default_rng(2)
    # Two groups apart along x only, so the line between them is near x = 0.
    left = np.column_stack([rng.normal(-3, 0.5, 60), rng.normal(0, 1.5, 60)])
    right = np.column_stack([rng.normal(3, 0.5, 60), rng.normal(0, 1.5, 60)])
    coordinates = np.vstack([left, right])
    lines = cluster_boundaries(coordinates, [0] * 60 + [1] * 60)
    assert lines
    xs = [x for line in lines for x, _ in line]
    assert -1.5 < min(xs) and max(xs) < 1.5                      # between the two groups
    assert cluster_boundaries(coordinates, [0] * 120) == []        # one cluster: none


def test_the_picture_carries_both():
    picture = visualise(_frame(300), id_column="id", class_column="k", numeric=["n1", "n2"],
                        categorical=["c1"], method="pca", clusters=3, outliers="lof",
                        outlier_share=2.0, boundaries=True)
    assert picture["outlier_count"] == 6 and sum(p["outlier"] for p in picture["points"]) == 6
    assert all(isinstance(p["outlier_score"], float) for p in picture["points"])
    assert picture["boundaries"] and all(len(line) >= 2 for line in picture["boundaries"])
    plain = visualise(_frame(300), id_column="id", class_column="k", numeric=["n1", "n2"],
                      categorical=["c1"], method="pca", clusters=0, boundaries=True)
    assert plain["boundaries"] == [] and plain["points"][0]["outlier"] is None


def test_the_settings_are_checked():
    check_settings("pca", 3, 1000, "random", "iforest", 2.0)
    for outliers, share in (("dbscan", 2.0), ("lof", 0.2), ("lof", 12.0)):
        with pytest.raises(VisualisationRefused):
            check_settings("pca", 3, 1000, "random", outliers, share)


def test_the_route_and_the_page(tmp_path):
    pytest.importorskip("fastapi")
    from test_revision_288a_project_runs import _client, _setup
    from test_revision_301a_share_sliders import IMBALANCED
    with _client(tmp_path) as client:
        project, dataset, _ = _setup(client, data=IMBALANCED)
        base = f"/api/projects/{project}/datasets/{dataset}/visualisation"
        drawn = client.get(base, params={"clusters": 2, "sample_size": 100, "outliers": "iforest",
                                         "outlier_share": 5, "boundaries": "true"}).json()
        refused = client.get(base, params={"outliers": "iforest", "outlier_share": 20})
        client.post(f"/ui/projects/{project}/open")
        page = client.get(f"/ui/dataset?dataset={dataset}&view=visualisation").text
    assert drawn["outlier_count"] == 1 and isinstance(drawn["boundaries"], list)
    assert refused.status_code == 422 and refused.json()["detail"] == "outlier_share"
    assert '<option value="iforest">Isolation Forest</option>' in page
    assert '<option value="lof">Local Outlier Factor</option>' in page
    assert 'name="boundaries" value="true" checked' in page and "Linjer mellan klustren" in page


def test_the_script_and_the_guides():
    script = (ROOT / "src" / "web" / "static" / "jbg.js").read_text(encoding="utf-8")
    assert '"&boundaries=" + (fields.get("boundaries") ? "true" : "false")' in script
    assert 'ring.setAttribute("class", "viz-outlier");' in script
    assert 'path.setAttribute("class", "viz-boundary");' in script
    sv = " ".join((ROOT / "docs" / "user_guide.sv.md").read_text(encoding="utf-8").split())
    assert "**Avvikelser** markerar de mest ovanliga raderna med en röd ring" in sv
    assert "**Linjer mellan klustren** ritar streckade linjer" in sv
