"""301c: the Run History tab (Körhistorik). Decided 2026-11-24: every run in
one list with filters, the settings a run used against the configuration's
current version, two runs compared, and rerun of training runs and feature
investigations with the same configuration version and dataset. No notes."""
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from JBGApplicationContracts import DataSourceKind, RunReference, RunStatus  # noqa: E402
from JBGIdentity import AuthenticatedPrincipal, AuthenticationMode  # noqa: E402
from test_revision_288a_project_runs import _client, _setup  # noqa: E402

OWNER = AuthenticatedPrincipal(AuthenticationMode.LOCAL, "developer").principal_key
ROOT = Path(__file__).resolve().parent.parent


def _finish(client, run_id, status=RunStatus.SUCCEEDED):
    store = client.app.state.jbg["store"]
    run = RunReference(run_id)
    store.claim(run, "w")
    store.finish(run, "w", status, result={"schema_version": 1} if status is RunStatus.SUCCEEDED
                 else None, **({} if status is RunStatus.SUCCEEDED else {"error_type": "X"}))
    return run_id


def _train(client, project, configuration, **extra):
    response = client.post(f"/api/projects/{project}/runs",
                           json=dict({"configuration_id": configuration}, **extra))
    assert response.status_code == 201, response.text
    return response.json()["run_id"]


def _two_versions(client):
    """A run on version 0, the row limit changed (version 1), a run on version 1."""
    project, dataset, configuration = _setup(client)
    client.post(f"/ui/projects/{project}/open")
    first = _finish(client, _train(client, project, configuration))
    client.put(f"/api/projects/{project}/configurations/{configuration}",
               json={"settings": {"debug": {"data_limit": 2}}, "expected_version": 0})
    second = _finish(client, _train(client, project, configuration))
    return project, dataset, configuration, first, second


def test_the_tab_lists_every_run_with_filters(tmp_path):
    with _client(tmp_path) as client:
        project, dataset, configuration, first, second = _two_versions(client)
        store = client.app.state.jbg["store"]
        failed = store.create(OWNER, DataSourceKind.CSV, {"spec_version": 1, "project_run": {
            "project_id": project, "kind": "investigation", "configuration_id": configuration,
            "configuration_version": 1, "configuration_name": "Standard",
            "dataset_id": dataset}}).key
        _finish(client, failed, RunStatus.FAILED)
        page = client.get("/ui/history").text
        investigations = client.get("/ui/history?kind=investigation").text
        succeeded = client.get("/ui/history?status=succeeded").text
        nothing = client.get("/ui/history?kind=prediction").text
    assert '<a href="/ui/history"' in page and "Körhistorik" in page
    assert 'class="off"' not in page.split("Körhistorik")[0][-200:]       # no longer greyed
    for run in (first, second, failed):
        assert f'value="{run}"' in page
    assert f'value="{failed}"' in investigations and f'value="{first}"' not in investigations
    assert f'value="{first}"' in succeeded and f'value="{failed}"' not in succeeded
    assert "Inga körningar matchar filtren." in nothing
    assert "Standard v0" in page and "Standard v1" in page


def test_a_run_shows_the_settings_against_the_current_version(tmp_path):
    with _client(tmp_path) as client:
        project, dataset, configuration, first, second = _two_versions(client)
        older = client.get(f"/ui/history?run={first}").text
        newer = client.get(f"/ui/history?run={second}").text
    assert "Inställningar jämfört med konfigurationens nuvarande version" in older
    differs = older.split("Inställningar jämfört")[1].split("Kolumnroller jämfört")[0]
    assert "<td>–</td><td>2</td>" in differs                         # the row limit: none, then 2
    assert "Konfigurationen har inte ändrats sedan den här körningen." in newer
    assert "Kolumnrollerna har inte ändrats sedan den här körningen." in older
    assert f'action="/ui/history/{first}/rerun"' in older and "Kör igen" in older


def test_changed_column_roles_are_shown(tmp_path):
    from jbg_test_roles import store_roles
    from test_revision_288a_project_runs import ROLES
    with _client(tmp_path) as client:
        project, dataset, configuration, first, _ = _two_versions(client)
        changed = {"connection": dict(ROLES["connection"], data_numerical_columns=["f1"],
                                      data_text_columns=["f2"])}
        store_roles(client, project, dataset, changed)
        page = client.get(f"/ui/history?run={first}").text
    roles = page.split("Kolumnroller jämfört med datasetets nuvarande roller")[1]
    assert "Numeriska variabler" in roles and "<td>f1, f2</td><td>f1</td>" in roles
    assert "Textvariabler" in roles


def test_two_runs_are_compared(tmp_path):
    with _client(tmp_path) as client:
        project, dataset, configuration, first, second = _two_versions(client)
        page = client.get(f"/ui/history?compare={first}&compare={second}").text
        one = client.get(f"/ui/history?compare={first}").text
    assert "Två körningar jämförda" in page
    settings = page.split("Inställningar som skiljer sig")[1].split("Kolumnroller som skiljer sig")[0]
    assert "<td>–</td><td>2</td>" in settings
    assert "Körningarna använde samma kolumnroller." in page
    assert "Markera exakt två körningar för att jämföra." in one


def test_rerun_uses_the_same_version_and_dataset(tmp_path):
    with _client(tmp_path) as client:
        project, dataset, configuration, first, second = _two_versions(client)
        done = client.post(f"/ui/history/{first}/rerun", follow_redirects=False)
        new = done.headers["location"].split("run=")[1].split("&")[0]
        spec = client.app.state.jbg["store"].get(RunReference(new)).spec["project_run"]
        busy = client.post(f"/ui/history/{second}/rerun", follow_redirects=False)
        busy_page = client.get(busy.headers["location"]).text
    assert done.status_code == 303 and "/ui/run?run=" in done.headers["location"]
    assert "message=started" in done.headers["location"]
    assert (spec["configuration_id"], spec["configuration_version"], spec["dataset_id"]) == \
        (configuration, 0, dataset)
    assert "message=run_in_progress" in busy.headers["location"]       # one run at a time
    from JBGWebUI import _load_catalog
    expected = _load_catalog("sv")["A run is queued or running in the project. Wait until it has finished."]
    assert expected in busy_page


def test_prediction_runs_are_not_rerun(tmp_path):
    with _client(tmp_path) as client:
        project, dataset, configuration, first, _ = _two_versions(client)
        store = client.app.state.jbg["store"]
        prediction = store.create(OWNER, DataSourceKind.CSV, {"spec_version": 1, "project_run": {
            "project_id": project, "kind": "prediction", "configuration_id": configuration,
            "configuration_version": 0, "dataset_id": dataset, "model_id": "m"}}).key
        _finish(client, prediction)
        page = client.get(f"/ui/history?run={prediction}").text
        refused = client.post(f"/ui/history/{prediction}/rerun", follow_redirects=False)
    assert "Kör igen" not in page and "Visa på fliken Prediktion" in page
    assert "message=not_rerunnable" in refused.headers["location"]


def test_the_helpers():
    from JBGWebUIHistory import (duration_text, interval_text, roles_from_snapshot, value_text,
                                 winning_pipeline)
    detail = {"columns": ["Oversampling", "Undersampling", "Preprocessor", "Feature Reduction",
                          "Algorithm (Library)", "Mean cv", "Stdev.", "Exception"],
              "rows": [["NOG", "NUG", "STA", "NOR", "LRN - Logistic Regression", 0.81, 0.1, ""],
                       ["SME", "NUG", "STA", "PCA", "SVC - Support Vector", 0.88, 0.1, ""],
                       ["NOG", "NUG", "NOS", "NOR", "KNN", 0.95, 0.1, "Error"]]}
    assert winning_pipeline(detail) == "SME · STA · PCA · SVC - Support Vector"
    assert duration_text({"created_at": "2026-11-24T10:00:00", "finished_at": "2026-11-24T10:03:07"},
                         "sv") == "3 min 7 s"
    assert duration_text({"created_at": "2026-11-24T10:00:00", "finished_at": None}, "sv") == "–"
    points = [{"value": 0.0020}, {"value": 0.0029}, {"value": None}]
    assert interval_text({"points": points}, "sv") == "0,20 % – 0,29 %"
    t = lambda text: {"Yes": "Ja", "No": "Nej", "All": "Alla"}.get(text, text)
    assert value_text(True, t, "sv") == "Ja" and value_text(None, t, "sv") == "–"
    assert value_text(["ALL"], t, "sv") == "Alla" and value_text(0.2, t, "sv") == "0,2"
    roles = roles_from_snapshot({"connection": {"id_column": "id", "class_column": "k",
                                                "data_numerical_columns": ["a"],
                                                "data_text_columns": ["b", "c", "d", "g"]},
                                 "mode": {"category_text_columns": ["c"], "date_columns": "d",
                                          "validation_group_column": "g", "categorical_limit": 30}})
    assert (roles["text"], roles["categorical"], roles["date"], roles["group_column"]) == \
        (["b"], ["c"], ["d"], "g")


def test_the_guides_describe_the_tab():
    sv = (ROOT / "docs" / "user_guide.sv.md").read_text(encoding="utf-8")
    en = (ROOT / "docs" / "user_guide.en.md").read_text(encoding="utf-8")
    assert "\n## Körhistorik\n" in sv and "\n## Run History\n" in en
