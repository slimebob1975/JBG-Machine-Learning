"""300r (asked 2026-11-23): datasets and configurations can be renamed.

Agreed 2026-11-23: a separate rename field, so a configuration's new name makes
no new version; runs show the configuration's current name (a run whose
configuration is deleted keeps the name it was started with, models keep the
name they were registered with); a rename counts as a change for the list
order and the project."""
from datetime import timedelta

import pytest

pytest.importorskip("fastapi")

from JBGApplicationContracts import DataSourceKind, RunReference  # noqa: E402
from JBGIdentity import AuthenticatedPrincipal, AuthenticationMode  # noqa: E402
from test_revision_288a_project_runs import CSV, _setup  # noqa: E402

OWNER = AuthenticatedPrincipal(AuthenticationMode.LOCAL, "developer").principal_key


def _client(tmp_path):
    from fastapi.testclient import TestClient
    from JBGFastAPIServer import create_server_app
    from JBGMetadataStore import MetadataStoreSettings
    from JBGSQLServer import SQLServerSettings
    return TestClient(create_server_app(
        settings=MetadataStoreSettings(sqlite_path=tmp_path / "jobs.sqlite"),
        run_logs=tmp_path / "run-logs", csv_root=tmp_path / "csv", model_root=tmp_path / "models",
        results_root=tmp_path / "runs", sql_server=SQLServerSettings(),
        dispatcher_options={"poll_seconds": 60, "heartbeat_seconds": 1,
                            "stale_after": timedelta(minutes=5)}))


def _run(client, project, *, finish=False, **meta):
    from JBGApplicationContracts import RunStatus
    store = client.app.state.jbg["store"]
    run = store.create(OWNER, DataSourceKind.CSV, {"spec_version": 1, "project_run": dict(
        {"project_id": project, "configuration_name": "Standard",
         "configuration_version": 1}, **meta)})
    if finish:
        store.claim(run, "w")
        store.finish(run, "w", RunStatus.SUCCEEDED, result={"schema_version": 1})
    return run.key


def _listed(client, project):
    from JBGDurableRuns import DurableRunService
    service = DurableRunService(client.app.state.jbg["store"], scope_for=lambda principal: None)
    return {r["run_id"]: r for r in service.list_project_runs(OWNER, project)}


# --- The API ----------------------------------------------------------------------------

def test_renaming_a_configuration_makes_no_new_version(tmp_path):
    with _client(tmp_path) as client:
        project, _, configuration = _setup(client)
        other = client.post(f"/api/projects/{project}/configurations",
                            json={"name": "Annan", "settings": {}}).json()["configuration_id"]
        url = f"/api/projects/{project}/configurations/{configuration}"
        before = client.get(url).json()
        renamed = client.patch(url, json={"name": "  Logistisk regression  "})
        listed = client.get(f"/api/projects/{project}/configurations").json()
        same_case = client.patch(url, json={"name": "LOGISTISK REGRESSION"})
        taken = client.patch(url, json={"name": "annan"})
        empty = client.patch(url, json={"name": "   "})
        unknown = client.patch(f"/api/projects/{project}/configurations/"
                               "00000000-0000-4000-8000-000000000000", json={"name": "X"})
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["name"] == "Logistisk regression"
    assert renamed.json()["version"] == before["version"] == 0
    assert renamed.json()["settings"] == before["settings"]
    assert listed[0]["configuration_id"] == configuration          # a rename is a change
    assert other in {c["configuration_id"] for c in listed}
    assert same_case.status_code == 200                              # its own name, new case
    assert taken.status_code == 409 and empty.status_code == 422
    assert unknown.status_code == 404


def test_renaming_a_dataset(tmp_path):
    with _client(tmp_path) as client:
        project, dataset, _ = _setup(client)
        client.post(f"/api/projects/{project}/datasets/csv", data={"name": "Tabell 2026",
                    "role": "mixed"}, files={"file": ("t.csv", CSV, "text/csv")})
        url = f"/api/projects/{project}/datasets/{dataset}"
        before = client.get(url).json()
        renamed = client.patch(url, json={"name": "Ärenden 2025"})
        taken = client.patch(url, json={"name": "TABELL 2026"})
        nothing = client.patch(url, json={})
        both = client.patch(url, json={"name": "Ärenden", "role": "mixed"})
        roles = client.get(url + "/roles")
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["name"] == "Ärenden 2025"
    for key in ("role", "registration_id", "active_training", "validation_state"):
        if key in before:
            assert renamed.json()[key] == before[key], key
    assert taken.status_code == 409 and nothing.status_code == 422
    assert both.status_code == 200
    assert both.json()["name"] == "Ärenden" and both.json()["role"] == "mixed"
    assert roles.status_code == 200                                  # the roles stay


def test_a_rename_counts_as_a_change_for_the_project(tmp_path):
    with _client(tmp_path) as client:
        project, dataset, _ = _setup(client)
        second = client.post("/api/projects", json={"name": "Senare", "source": "csv"}).json()
        before = client.get(f"/api/projects/{project}").json()["updated_at"]
        client.patch(f"/api/projects/{project}/datasets/{dataset}", json={"name": "Nytt namn"})
        after = client.get(f"/api/projects/{project}").json()["updated_at"]
    assert second["project_id"] != project and after > before


# --- The forms --------------------------------------------------------------------------

def test_the_configuration_tab_renames(tmp_path):
    with _client(tmp_path) as client:
        project, _, configuration = _setup(client)
        client.post(f"/api/projects/{project}/configurations", json={"name": "Annan",
                                                                    "settings": {}})
        client.post(f"/ui/projects/{project}/open")
        page = client.get(f"/ui/configuration?configuration={configuration}").text
        done = client.post(f"/ui/configuration/{configuration}/rename",
                           data={"name": "Ny konfiguration"}, follow_redirects=False)
        shown = client.get(done.headers["location"]).text
        taken = client.post(f"/ui/configuration/{configuration}/rename",
                            data={"name": "annan"}, follow_redirects=False)
        empty = client.post(f"/ui/configuration/{configuration}/rename",
                            data={"name": " "}, follow_redirects=False)
        version = client.get(f"/api/projects/{project}/configurations/{configuration}").json()
    assert "Byt namn på konfigurationen" in page
    assert f'action="/ui/configuration/{configuration}/rename"' in page
    assert 'value="Standard"' in page
    assert done.status_code == 303 and "message=renamed" in done.headers["location"]
    assert "Konfigurationen har bytt namn." in shown and "Ny konfiguration" in shown
    assert "message=duplicate" in taken.headers["location"]
    assert "message=bad_name" in empty.headers["location"]
    assert version["name"] == "Ny konfiguration" and version["version"] == 0


def test_the_dataset_tab_renames(tmp_path):
    with _client(tmp_path) as client:
        project, dataset, _ = _setup(client)
        client.post(f"/ui/projects/{project}/open")
        page = client.get(f"/ui/dataset?dataset={dataset}").text
        done = client.post(f"/ui/dataset/{dataset}/rename", data={"name": "Ärenden"},
                           follow_redirects=False)
        shown = client.get(done.headers["location"]).text
        empty = client.post(f"/ui/dataset/{dataset}/rename", data={"name": ""},
                            follow_redirects=False)
        unknown = client.post("/ui/dataset/00000000-0000-4000-8000-000000000000/rename",
                              data={"name": "X"}, follow_redirects=False)
    assert "Byt namn på datasetet" in page and f'action="/ui/dataset/{dataset}/rename"' in page
    assert "message=renamed" in done.headers["location"]
    assert "Datasetet har bytt namn." in shown and "<b>Ärenden</b>" in shown
    assert "message=bad_name" in empty.headers["location"]
    assert "message=unavailable" in unknown.headers["location"]


# --- Runs show the current name ---------------------------------------------------------

def test_runs_show_the_configurations_current_name(tmp_path):
    with _client(tmp_path) as client:
        project, dataset, configuration = _setup(client)
        client.post(f"/ui/projects/{project}/open")
        training = _run(client, project, kind="training", dataset_id=dataset,
                        configuration_id=configuration, model_id="m-1", finish=True)
        # A prediction run from before 300r: no configuration ID, only its model.
        prediction = _run(client, project, kind="prediction", dataset_id=dataset,
                          model_id="m-1", finish=True)
        client.patch(f"/api/projects/{project}/configurations/{configuration}",
                     json={"name": "Ny konfiguration"})
        run_tab = client.get("/ui/run").text
        prediction_tab = client.get("/ui/prediction").text
        overview = client.get("/ui/overview").text
        delete_page = client.get(f"/ui/runs/{training}/delete").text
        listed = _listed(client, project)
        # The model is still in use, so its training run is hidden (299e).
        client.app.state.jbg["store"].hide(RunReference(training))
        hidden_training = client.get("/ui/prediction").text
        after_hiding = _listed(client, project)
    assert "Ny konfiguration v1" in run_tab and "Standard v1" not in run_tab
    assert "Ny konfiguration v1" in prediction_tab
    assert "Ny konfiguration" in overview
    assert "Ny konfiguration v1" in delete_page
    assert listed[prediction]["configuration_id"] == configuration
    assert training not in after_hiding
    assert after_hiding[prediction]["configuration_id"] == configuration
    assert "Ny konfiguration v1" in hidden_training


def test_a_deleted_configuration_keeps_the_started_name():
    from JBGWebUIRun import configuration_names, with_configuration_names

    class Configurations:
        def list(self, owner, project):
            return [{"configuration_id": "c-2", "name": "Ny"}]
    items = [{"configuration_id": "c-1", "configuration_name": "Gammal"},
             {"configuration_id": "c-2", "configuration_name": "Standard"},
             {"configuration_name": "Utan ID"}]
    with_configuration_names(items, configuration_names(Configurations(), "o", "p"))
    assert [i["configuration_name"] for i in items] == ["Gammal", "Ny", "Utan ID"]

    class Broken:
        def list(self, owner, project):
            raise RuntimeError("unavailable")
    assert configuration_names(Broken(), "o", "p") == {}


def test_renamed_datasets_show_in_run_lists(tmp_path):
    with _client(tmp_path) as client:
        project, dataset, configuration = _setup(client)
        client.post(f"/ui/projects/{project}/open")
        _run(client, project, kind="training", dataset_id=dataset,
             configuration_id=configuration)
        client.patch(f"/api/projects/{project}/datasets/{dataset}", json={"name": "Ärenden"})
        page = client.get("/ui/run").text
    assert "<b>Ärenden</b><br>" in page


def test_new_prediction_runs_record_their_configuration():
    from pathlib import Path
    source = (Path(__file__).resolve().parent.parent / "src" / "JBGProjectRuns.py") \
        .read_text(encoding="utf-8")
    assert source.count('"configuration_id": trained.get("configuration_id"),      # 300r') == 3
