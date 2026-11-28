"""301w (asked 2026-11-27): a run's own processes and memory, sampled by its
worker every five seconds into resources.jsonl in the run's folder; a live
chart on the Training tab while there are no results, and each recent run's
peak memory, peak processes and duration on the Overview."""
import json
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from JBGRunResources import FILENAME, INTERVAL, ResourceSampler, read, sample, summary

ROOT = Path(__file__).resolve().parent.parent


def test_the_sampler_counts_the_process_tree(tmp_path):
    assert INTERVAL == 5.0
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(5)"])
    try:
        found = sample()
        assert found["processes"] >= 2 and found["memory_mb"] > 1
    finally:
        child.kill()
        child.wait()
    with ResourceSampler(tmp_path, interval=0.05):
        time.sleep(0.2)
    samples = read(tmp_path)
    assert len(samples) >= 3 and {"t", "s", "processes", "memory_mb"} <= set(samples[0])
    peaks = summary(samples)
    assert peaks["samples"] == len(samples) and peaks["peak_processes"] >= 1
    assert summary([]) is None and read(tmp_path / "missing") == []


def test_a_failure_never_reaches_the_run(tmp_path):
    blocked = tmp_path / "file"
    blocked.write_text("not a folder")
    with ResourceSampler(blocked / "run", interval=0.05):          # cannot be created
        time.sleep(0.1)
    with ResourceSampler(None):                                    # runs outside a project
        pass


def test_the_worker_samples_every_run():
    worker = (ROOT / "src" / "JBGRunWorker.py").read_text(encoding="utf-8")
    assert "ResourceSampler(_run_folder(record, results_root, run)):" in worker


def _running_run(client, project, dataset, configuration, samples):
    from JBGApplicationContracts import DataSourceKind, RunReference
    from JBGIdentity import AuthenticatedPrincipal, AuthenticationMode
    owner = AuthenticatedPrincipal(AuthenticationMode.LOCAL, "developer").principal_key
    store = client.app.state.jbg["store"]
    key = store.create(owner, DataSourceKind.CSV, {"spec_version": 1, "project_run": {
        "project_id": project, "kind": "training", "configuration_id": configuration,
        "configuration_version": 0, "dataset_id": dataset}}).key
    store.claim(RunReference(key), "w")
    return key


def _client_with_results(tmp_path):
    """The 288a test client, with the run folders under tmp_path."""
    from fastapi.testclient import TestClient
    from JBGFastAPIServer import create_server_app
    from JBGMetadataStore import MetadataStoreSettings
    from JBGSQLServer import SQLServerSettings
    from test_revision_288a_project_runs import _Launcher
    options = {"poll_seconds": 60, "heartbeat_seconds": 1, "stale_after": timedelta(minutes=5),
               "launcher": _Launcher()}
    return TestClient(create_server_app(
        settings=MetadataStoreSettings(sqlite_path=tmp_path / "jobs.sqlite"), subject="developer",
        run_logs=tmp_path / "run-logs", csv_root=tmp_path / "csv", model_root=tmp_path / "models",
        sql_server=SQLServerSettings(), results_root=tmp_path / "runs",
        dispatcher_options=options))


def test_the_training_tab_and_the_overview(tmp_path):
    pytest.importorskip("fastapi")
    from test_revision_288a_project_runs import _setup
    with _client_with_results(tmp_path) as client:
        project, dataset, configuration = _setup(client)
        client.post(f"/ui/projects/{project}/open")
        run = _running_run(client, project, dataset, configuration, None)
        page = client.get(f"/ui/run?run={run}").text
        empty = client.get(f"/ui/runs/{run}/resources").json()
        target = tmp_path / "runs" / project / run
        target.mkdir(parents=True, exist_ok=True)
        (target / FILENAME).write_text("\n".join(json.dumps(s) for s in (
            {"s": 0, "processes": 1, "memory_mb": 100.0}, {"s": 65, "processes": 7, "memory_mb": 812.6},
            {"s": 130, "processes": 2, "memory_mb": 300.0})) + "\n", encoding="utf-8")
        found = client.get(f"/ui/runs/{run}/resources").json()
        overview = client.get("/ui/overview").text
        other = client.get("/ui/runs/00000000-0000-4000-8000-000000000000/resources")
    assert f'data-resources="/ui/runs/{run}/resources"' in page and "Processer och minne" in page
    assert empty["samples"] == [] and empty["status"] == "running"
    assert found["summary"] == {"peak_memory_mb": 812.6, "peak_processes": 7, "duration_s": 130,
                                "samples": 3}
    assert "Processer och minne för de senaste körningarna" in overview
    assert ">813<" in overview and ">7<" in overview and "2 min 10 s" in overview
    assert other.status_code == 404


def test_the_script():
    script = (ROOT / "src" / "web" / "static" / "jbg.js").read_text(encoding="utf-8")
    assert 'document.querySelectorAll("[data-resources]").forEach(wireResources);' in script
    assert "if (RUN_DONE.indexOf(found.status) < 0) { setTimeout(poll, 5000); }" in script
