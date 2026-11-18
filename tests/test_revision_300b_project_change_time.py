"""300b (asked 2026-11-18): the Projects list is ordered by last change, and
every change inside a project counts: datasets (new, roles, validation, role,
corrections, deletion), configurations (new, saved, deleted), runs started
and deletions, not only edits of the project's own details."""
import time
from datetime import timedelta
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")

from JBGApplicationContracts import DataSourceKind, RunStatus  # noqa: E402
from JBGIdentity import AuthenticatedPrincipal, AuthenticationMode  # noqa: E402
from test_revision_288a_project_runs import CSV  # noqa: E402

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


def _order(client):
    return [p["name"] for p in client.get("/api/projects").json()]


def _new(client, name):
    return client.post("/api/projects", json={"name": name, "source": "csv"}).json()["project_id"]


def test_changes_inside_a_project_move_it_to_the_top(tmp_path):
    with _client(tmp_path) as client:
        older = _new(client, "Older")
        time.sleep(0.02)
        _new(client, "Newer")
        assert _order(client) == ["Newer", "Older"]
        dataset = client.post(f"/api/projects/{older}/datasets/csv",
                              data={"name": "D", "role": "training"},
                              files={"file": ("d.csv", CSV, "text/csv")}).json()["dataset_id"]
        assert _order(client)[0] == "Older"                         # a new dataset
        repository = client.app.state.jbg["datasets"]
        for label, action in (
            ("configuration", lambda: client.post(f"/api/projects/{older}/configurations",
                                                  json={"name": "C"})),
            ("roles", lambda: repository.set_roles(OWNER, older, dataset, _roles())),
        ):
            time.sleep(0.02)
            _new(client, f"Bump {label}")
            assert _order(client)[0] == f"Bump {label}"
            time.sleep(0.02)
            action()
            assert _order(client)[0] == "Older", label


def _roles():
    from JBGDatasetRoles import DatasetRoles
    return DatasetRoles.from_mapping({"row_id": "id", "target": "class", "f1": "numeric",
                                      "f2": "numeric"})


def test_a_failed_change_does_not_count(tmp_path):
    with _client(tmp_path) as client:
        older = _new(client, "Older")
        time.sleep(0.02)
        _new(client, "Newer")
        with pytest.raises(KeyError):
            client.app.state.jbg["datasets"].delete(OWNER, older,
                                                    "00000000-0000-4000-8000-000000000000")
        assert _order(client) == ["Newer", "Older"]                # rolled back


def test_a_submitted_run_and_a_deletion_count():
    from JBGProjectRuns import ProjectRunService, _touching
    touched = []
    service = object.__new__(ProjectRunService)
    service._projects = SimpleNamespace(touch=lambda owner, pid: touched.append((owner, pid)))

    @_touching
    def submit(self, principal, project_id, **kwargs):
        return {"run_id": "r"}
    assert submit(service, SimpleNamespace(principal_key="o"), "p") == {"run_id": "r"}
    assert touched == [("o", "p")]
    assert ProjectRunService.submit.__wrapped__ and ProjectRunService.submit_prediction.__wrapped__


def test_deleting_a_run_counts(tmp_path):
    with _client(tmp_path) as client:
        older = _new(client, "Older")
        client.post(f"/ui/projects/{older}/open")
        store = client.app.state.jbg["store"]
        run = store.create(OWNER, DataSourceKind.CSV, {"spec_version": 1, "project_run": {
            "project_id": older, "kind": "prediction", "configuration_name": "C"}})
        store.claim(run, "w")
        store.finish(run, "w", RunStatus.SUCCEEDED, result={"schema_version": 1})
        time.sleep(0.02)
        _new(client, "Newer")
        assert _order(client)[0] == "Newer"
        time.sleep(0.02)
        client.post(f"/ui/runs/{run.key}/delete", data={"back": "/ui/prediction"})
        assert _order(client)[0] == "Older"
