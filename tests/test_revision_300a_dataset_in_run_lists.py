"""300a (asked 2026-11-18): the run lists on the Training and Prediction tabs
show each run's dataset as well as its configuration ("Dataset /
Konfiguration"), so runs of one configuration on several tables with the same
structure can be told apart."""
import re
from datetime import timedelta

import pytest

pytest.importorskip("fastapi")

from JBGApplicationContracts import DataSourceKind  # noqa: E402
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


def test_the_run_lists_name_the_dataset(tmp_path):
    with _client(tmp_path) as client:
        project, first, configuration = _setup(client)
        second = client.post(f"/api/projects/{project}/datasets/csv",
                             data={"name": "Tabell 2026", "role": "mixed"},
                             files={"file": ("t.csv", CSV, "text/csv")}).json()["dataset_id"]
        client.post(f"/ui/projects/{project}/open")
        store = client.app.state.jbg["store"]
        names = {}
        for dataset, kind in ((first, "training"), (second, "training"), (second, "prediction")):
            run = store.create(OWNER, DataSourceKind.CSV, {"spec_version": 1, "project_run": {
                "project_id": project, "kind": kind, "dataset_id": dataset,
                "configuration_name": "Standard", "configuration_version": 1}})
            names[(dataset, kind)] = run.key
        first_name = next(d["name"] for d in client.get(f"/api/projects/{project}/datasets").json()
                          if d["dataset_id"] == first)
        training = client.get("/ui/run").text
        assert "<th>Dataset / Konfiguration</th>" in training
        assert f"<b>{first_name}</b><br><span class=\"muted\">Standard v1</span>" in training
        assert "<b>Tabell 2026</b><br><span class=\"muted\">Standard v1</span>" in training
        prediction = client.get("/ui/prediction").text
        assert "<b>Tabell 2026</b><br><span class=\"muted\">Standard v1</span>" in prediction
        assert first_name not in re.sub(r"<select.*?</select>", "", prediction, flags=re.S) \
            .split("<tbody>")[1].split("</tbody>")[0]


def test_a_run_without_a_known_dataset_shows_the_configuration_only():
    from JBGWebUIRun import with_dataset_names

    class Broken:
        def list(self, *args):
            raise RuntimeError("unavailable")
    items = with_dataset_names([{"dataset_id": "x"}], Broken(), "o", "p")
    assert items[0]["dataset_name"] == ""
