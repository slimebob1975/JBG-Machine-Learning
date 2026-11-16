"""299i (agreed 2026-11-13): the feature investigation as a run of its own.

Started on the Training tab ("Undersök variabler") with the active training
dataset and the chosen configuration, whose feature investigation settings
are used again (only Voila's mode and saved profile stay inactive). A worker
runs the engine's investigation on the training part; no model, no
predictions. More than two classes: the target class against the rest.
Refused while the dataset has a group column. The run panel shows the
recommendation in numbers; names stay in the run folder (investigation.json).
"""
import csv
import io
import json
import re
import time
from datetime import timedelta
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("jinja2")

from JBGApplicationContracts import RunReference, RunStatus  # noqa: E402
from JBGIdentity import AuthenticatedPrincipal, AuthenticationMode  # noqa: E402
from test_revision_288a_project_runs import ROLES, _setup  # noqa: E402

OWNER = AuthenticatedPrincipal(AuthenticationMode.LOCAL, "developer")


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


def _open(client, project, configuration):
    client.post(f"/ui/projects/{project}/open")
    client.post(f"/ui/configuration/{configuration}/select")


# --- The settings ------------------------------------------------------------------------

def test_presets_decide_the_budget_and_custom_uses_the_values():
    from JBGFeatureSearchPresets import PRESETS
    from JBGRunInvestigation import search_budget
    mode = SimpleNamespace(feature_search_preset="Standard", feature_search_trials=2,
                           feature_search_sizes=[3], feature_search_inner_folds=2,
                           feature_search_outer_folds=2, feature_search_top_sets=1,
                           feature_search_refine_rounds=0, feature_search_max_evaluations=3,
                           feature_search_min_gain=0.01)
    assert search_budget(mode) == PRESETS["Standard"]
    mode.feature_search_preset = "Custom"
    assert search_budget(mode)["trials"] == 2 and search_budget(mode)["sizes"] == [3]


def test_an_investigation_only_trains():
    from JBGRunInvestigation import investigation_config
    mode = SimpleNamespace(train=False, predict=True, mispredicted=True,
                           calculate_dark_numbers=True, calculate_feature_importance=True)
    run = investigation_config(SimpleNamespace(mode=mode))
    assert (run.mode.train, run.mode.predict, run.mode.mispredicted,
            run.mode.calculate_dark_numbers, run.mode.calculate_feature_importance) == \
        (True, False, False, False, False)
    assert mode.predict is True                                   # the original is unchanged


def test_the_store_gets_numbers_only():
    import numpy as np
    from JBGRunInvestigation import _plain, summary
    result = _plain({"recommendation": {"selected_columns": ["a", "b"]},
                     "original_columns": ["a", "b", "c"], "target": "virginica",
                     "nested_validation": {"selected": {"mean_mcc": np.float64(0.61)},
                                           "full_baseline": {"mean_mcc": np.float64(0.58)}},
                     "one_vs_rest": {"target": "virginica", "rest_label": "(other classes)"}})
    stored = summary(result)
    assert stored == {"schema_version": 1, "kind": "investigation", "selected_count": 2,
                      "original_count": 3, "selected_mcc": 0.61, "baseline_mcc": 0.58,
                      "one_vs_rest": True}
    assert "virginica" not in json.dumps(stored) and "a" not in stored


def test_the_overview_shows_the_reviewed_numbers_only():
    from JBGRunOverview import INNER_KINDS, project_run_overview
    from JBGStructuredEvaluation import TASK_STAGES
    assert "feature_investigation" in TASK_STAGES and "feature_subsets" in INNER_KINDS
    overview = project_run_overview("r", RunStatus.SUCCEEDED, (), {
        "kind": "investigation", "selected_count": 2, "original_count": 3,
        "selected_mcc": 0.61, "baseline_mcc": 7, "one_vs_rest": True, "columns": ["x"]})
    assert overview["results"]["investigation"] == {
        "selected_count": 2, "original_count": 3, "selected_mcc": 0.61, "baseline_mcc": None,
        "one_vs_rest": True}


def test_search_events_become_progress_and_cancel_checks():
    from JBGRunInvestigation import Progress
    calls = []
    observed = SimpleNamespace(
        start_inline_progress=lambda key, description, total, tip: calls.append(("start", total)),
        update_inline_progress=lambda key, done, text: calls.append(("update", done)),
        end_inline_progress=lambda key, set_100=True: calls.append(("end",)),
        _inner_checkpoint=lambda: calls.append(("check",)))
    progress = Progress(observed)
    progress({"event": "fit_started"})
    progress({"event": "candidate_completed", "scope": "search", "candidate": 1, "max_evaluations": 5})
    progress({"event": "candidate_completed", "scope": "search", "candidate": 2, "max_evaluations": 5})
    progress({"event": "candidate_completed", "scope": "outer_1", "candidate": 1, "max_evaluations": 5})
    assert calls == [("check",), ("start", 5), ("update", 1), ("update", 2), ("end",),
                     ("start", 5), ("update", 1)]


# --- Starting one ------------------------------------------------------------------------

def test_an_investigation_is_a_run_without_a_model(tmp_path):
    with _client(tmp_path) as client:
        settings = json.loads(json.dumps(ROLES))
        settings["mode"] = {"predict": True}                   # an investigation never predicts
        project, dataset, configuration = _setup(client, roles=settings)
        _open(client, project, configuration)
        page = client.get("/ui/run").text
        assert '<form method="post" action="/ui/run/investigate"><button class="btn act ready">Undersök variabler</button></form>' in page
        started = client.post("/ui/run/investigate", follow_redirects=False)
        assert "message=investigation_started" in started.headers["location"]
        run_id = re.search(r"run=([0-9a-f-]{36})", started.headers["location"]).group(1)
        spec = client.app.state.jbg["store"].get(RunReference(run_id)).spec
        meta = spec["project_run"]
        assert meta["kind"] == "investigation" and "model_id" not in meta
        assert meta["dataset_id"] == dataset and meta["configuration_id"] == configuration
        assert spec["configuration"]["mode"]["predict"] is False
        stored = client.get(f"/api/projects/{project}/configurations/{configuration}").json()
        assert stored["settings"]["mode"]["predict"] is True       # the configuration is unchanged
        page = client.get(f"/ui/run?run={run_id}").text
        assert "Variabelundersökning" in page                      # marked in the run list
        assert run_id not in client.get("/ui/results").text


def test_a_dataset_with_a_group_column_is_refused(tmp_path):
    with _client(tmp_path) as client:
        project, dataset, configuration = _setup(client)
        roles = client.app.state.jbg["datasets"].get_roles(OWNER.principal_key, project, dataset)
        mapping = roles.as_mapping()
        feature = next(name for name, role in mapping.items() if role == "numeric")
        mapping[feature] = "group"
        from JBGDatasetRoles import DatasetRoles
        client.app.state.jbg["datasets"].set_roles(OWNER.principal_key, project, dataset,
                                                   DatasetRoles.from_mapping(mapping))
        _open(client, project, configuration)
        page = client.get("/ui/run").text
        assert ('<button class="btn act blocked" disabled title="Variabelundersökningen kan ännu '
                'inte hålla isär grupper, och datasetet har en gruppkolumn.">Undersök variabler'
                '</button>') in page
        refused = client.post("/ui/run/investigate", follow_redirects=False)
        assert refused.headers["location"] == "/ui/run?message=groups_not_supported"
        assert client.app.state.jbg["store"].list_for_owner(OWNER.principal_key) == ()


def test_the_section_shows_the_investigation_settings(tmp_path):
    with _client(tmp_path) as client:
        project, _, configuration = _setup(client)
        _open(client, project, configuration)
        page = client.get(f"/ui/configuration?configuration={configuration}").text
        assert "f:mode.feature_search_trials" in page and "f:mode.feature_selection_mode" not in page
        assert "används av variabelundersökningen, som startas med Undersök variabler" in page


def test_the_run_panel_shows_the_recommendation(tmp_path):
    with _client(tmp_path) as client:
        project, dataset, configuration = _setup(client)
        _open(client, project, configuration)
        store = client.app.state.jbg["store"]
        from JBGApplicationContracts import DataSourceKind
        run = store.create(OWNER.principal_key, DataSourceKind.CSV, {"spec_version": 1, "project_run": {
            "project_id": project, "kind": "investigation", "configuration_name": "Standard"}})
        store.claim(run, "w")
        store.finish(run, "w", RunStatus.SUCCEEDED, result={
            "schema_version": 1, "kind": "investigation", "selected_count": 2, "original_count": 4,
            "selected_mcc": 0.6123, "baseline_mcc": 0.5811, "one_vs_rest": True})
        page = client.get(f"/ui/run?run={run.key}").text
        assert "<b>Rekommendation:</b> 2 av 4 variabler." in page
        assert "MCC med rekommendationen 0,6123" in page and "med alla variabler 0,5811" in page
        assert "målklassen undersöktes mot de övriga klasserna" in page
        assert "Alla resultat för körningen" not in page


# --- The engine: the target class against the rest (native) ------------------------------

import test_revision_281c_csv_application_e2e as revision_281c  # noqa: E402
from test_revision_296b_csv_predictions import _wait_for_workers_to_exit  # noqa: E402


class FeatureInvestigationNative299i(revision_281c.CSVApplicationEndToEnd281c):
    test_registered_csv_trains_and_reloads_model_through_application = None
    test_other_scope_cannot_prepare_csv_run = None

    def test_an_investigation_runs_in_a_worker_and_keeps_its_result_in_the_run_folder(self):
        from fastapi.testclient import TestClient
        from JBGFastAPIServer import create_server_app
        from JBGMetadataStore import MetadataStoreSettings
        self._configure_training()
        self.config.mail.notification_email = ""
        with self.repo.open_artifact(self.scope, self.ref.artifact_id) as stream:
            text = stream.read().decode("utf-8-sig")
        rows = list(csv.reader(io.StringIO(text), csv.Sniffer().sniff(text.splitlines()[0])))
        class_at = rows[0].index(self.config.connection.class_column)
        classes = {row[class_at] for row in rows[1:] if row[class_at].strip()}
        work = self.root / "api"
        work.mkdir()
        client = TestClient(create_server_app(
            settings=MetadataStoreSettings(sqlite_path=work / "jobs.sqlite"),
            run_logs=work / "run-logs", csv_root=work / "csv", model_root=work / "models",
            results_root=work / "runs",
            dispatcher_options={"script_path": self.root, "heartbeat_seconds": 5,
                                "stale_after": timedelta(minutes=10), "poll_seconds": 1}))
        try:
            with client:
                settings = self.config._config_to_json(username="")
                settings["mode"].update(
                    predict=False, feature_search_preset="Custom", feature_search_trials=2,
                    feature_search_sizes=[2], feature_search_inner_folds=2,
                    feature_search_outer_folds=2, feature_search_top_sets=1,
                    feature_search_refine_rounds=0, feature_search_max_evaluations=3,
                    feature_search_model_type="Linear")
                project, _, configuration = _setup(client, data=text.encode("utf-8"),
                                                   roles=settings)
                _open(client, project, configuration)
                started = client.post("/ui/run/investigate", follow_redirects=False)
                self.assertIn("investigation_started", started.headers["location"])
                run_id = re.search(r"run=([0-9a-f-]{36})", started.headers["location"]).group(1)
                deadline, status = time.time() + 900, None
                while time.time() < deadline:
                    status = client.get(f"/api/runs/{run_id}").json()["status"]
                    if status in ("succeeded", "failed", "cancelled", "interrupted"):
                        break
                    time.sleep(1)
                log = work / "run-logs" / f"run_{run_id}.log"
                tail = log.read_bytes().decode("utf-8", "replace")[-3000:] if log.exists() else ""
                self.assertEqual(status, "succeeded", tail)
                overview = client.get(f"/api/runs/{run_id}/overview").json()
                found = overview["results"]["investigation"]
                self.assertGreaterEqual(found["selected_count"], 1)
                self.assertEqual(found["one_vs_rest"], len(classes) > 2)
                saved = json.loads((work / "runs" / project / run_id / "investigation.json")
                                   .read_text(encoding="utf-8"))
                self.assertTrue(saved["recommendation"]["selected_columns"])
                self.assertEqual("one_vs_rest" in saved, len(classes) > 2)
                self.assertEqual(client.get(f"/api/projects/{project}/models").json(), [])
                _wait_for_workers_to_exit(client)
        finally:
            client.close()
