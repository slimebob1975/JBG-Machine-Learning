"""300d (asked 2026-11-16/18): three small things at once.
1. While a run of the project is queued or running, the start buttons on the
   Training and Prediction tabs are red with the reason, and the start routes
   refuse.
2. The validation study also measures the hit rate: of the rows the model
   flags (registered as the rest, predicted as the target), the share truly
   hidden, and the lift against random selection (reported only).
3. The web worker's run log has a timestamp and a level on every line and no
   empty lines (Voila unchanged)."""
import io
import math
import re
from datetime import datetime, timedelta

import pandas as pd
import pytest

pytest.importorskip("fastapi")

from JBGApplicationContracts import DataSourceKind  # noqa: E402
from JBGIdentity import AuthenticatedPrincipal, AuthenticationMode  # noqa: E402
from JBGRunLogFormat import LineLogWriter, install, level_of  # noqa: E402
from test_revision_288a_project_runs import _setup  # noqa: E402

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


def test_starting_is_refused_while_a_run_is_in_progress(tmp_path):
    with _client(tmp_path) as client:
        project, dataset, configuration = _setup(client)
        client.post(f"/ui/projects/{project}/open")
        client.post(f"/ui/configuration/{configuration}/select")
        store = client.app.state.jbg["store"]
        store.create(OWNER, DataSourceKind.CSV, {"spec_version": 1, "project_run": {
            "project_id": project, "kind": "training", "dataset_id": dataset}})
        reason = "En körning står i kö eller pågår i projektet. Vänta tills den är klar."
        page = client.get("/ui/run").text
        assert f'disabled title="{reason}">Starta träning</button>' in page
        assert f'disabled title="{reason}">Undersök variabler</button>' in page
        for path in ("/ui/run", "/ui/run/investigate"):
            refused = client.post(path, follow_redirects=False)
            assert refused.headers["location"] == "/ui/run?message=run_in_progress"
        assert f'disabled title="{reason}">Starta prediktion</button>' in client.get(
            "/ui/prediction").text
        refused = client.post("/ui/prediction", follow_redirects=False)
        assert refused.headers["location"].startswith("/ui/prediction?message=")
        assert len(store.list_for_owner(OWNER)) == 1                    # nothing new


def test_the_study_measures_the_hit_rate():
    from JBGDarkNumberStudy import Cell, run_once, summarise
    rows = pd.DataFrame(run_once(Cell(0.10, 0.5, "strong", rows=1200), 3))
    assert {"flagged", "hit_rate", "lift"} <= set(rows.columns)
    test = rows[rows["estimate"] == "D_cv_test"].iloc[0]
    assert test["flagged"] > 0 and 0 <= test["hit_rate"] <= 1
    assert test["lift"] == pytest.approx(test["hit_rate"] / test["true_H"])
    summary = summarise(rows)
    assert {"hit_rate_pp", "lift"} <= set(summary.columns)
    assert summary["lift"].notna().all()


class _Clock:
    def __call__(self):
        return datetime(2026, 11, 18, 14, 3, 12)


def test_the_log_lines_get_a_timestamp_and_a_level():
    out = io.StringIO()
    writer = LineLogWriter(out, "INFO", clock=_Clock())
    writer.write(" -- Fetching data --\n\n\nData checked: 20 %")
    writer.write("\r\n[DEBUG] query omitted\nConvergenceWarning: not converged\n")
    writer.write("Traceback (most recent call last):\n   \n")
    writer.flush()
    assert out.getvalue().splitlines() == [
        "2026-11-18 14:03:12 INFO     -- Fetching data --",
        "2026-11-18 14:03:12 INFO    Data checked: 20 %",
        "2026-11-18 14:03:12 DEBUG   [DEBUG] query omitted",
        "2026-11-18 14:03:12 WARNING ConvergenceWarning: not converged",
        "2026-11-18 14:03:12 ERROR   Traceback (most recent call last):"]
    assert level_of("  File \"x.py\", line 3", "ERROR") == "ERROR"


def test_only_the_worker_program_installs_it():
    from pathlib import Path
    from types import SimpleNamespace
    source = (Path(__file__).resolve().parent.parent / "src" / "JBGRunWorker.py").read_text(
        encoding="utf-8")
    main_block = source.split('if __name__ == "__main__":')[1]
    assert "install(sys)" in main_block
    fake = SimpleNamespace(stdout=io.StringIO(), stderr=io.StringIO())
    install(fake)
    install(fake)                                                   # not twice
    assert isinstance(fake.stdout, LineLogWriter) and isinstance(fake.stderr, LineLogWriter)
    assert not isinstance(fake.stdout._stream, LineLogWriter)
