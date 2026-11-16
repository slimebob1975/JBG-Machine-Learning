"""299k (agreed 2026-11-13, mockup): the Overview as designed. All the user's
projects first (training runs, rows processed, models compared, models in
use, each with "of which in the open project"; runs per week; rows processed
per project), then the open project (today's cards, model quality per training
run with the average of the last three, rows processed per week, latest
runs). Charts are SVG drawn on the server. Rows processed and models compared
are recorded by the worker when a run finishes (no engine change).
"""
import re
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from JBGApplicationContracts import DataSourceKind, RunStatus  # noqa: E402
from JBGOverviewStats import overview_stats  # noqa: E402
from JBGWebUICharts import project_bars, quality_line, week_bars  # noqa: E402

NOW = datetime(2026, 11, 19, 12, tzinfo=timezone.utc)      # a Thursday


def _record(project, *, kind="training", status="succeeded", rows=0, models=0, days=0,
            scoring="mcc", evaluation=None, key=None):
    result = {"counts": {"rows": rows, "models": models}}
    if evaluation is not None:
        result["evaluation"] = evaluation
    return SimpleNamespace(
        spec={"project_run": {"project_id": project, "kind": kind, "configuration_name": "C"},
              "configuration": {"mode": {"scoring": scoring}}},
        status=RunStatus(status), result=result, created_at=NOW - timedelta(days=days),
        run=SimpleNamespace(key=key or f"{project}-{kind}-{days}-{rows}"))


def test_key_figures_cover_all_projects_and_the_open_one():
    records = [_record("p1", rows=100, models=12, evaluation={"mcc": 0.5}),
               _record("p1", kind="prediction", rows=40, days=1),
               _record("p2", rows=300, models=5, days=8),
               _record("p2", status="failed", rows=999, models=9, days=2),
               _record("foreign", rows=10_000)]                   # not one of the owner's
    stats = overview_stats(records, project_names={"p1": "Alpha", "p2": "Beta"},
                           open_project="p1", models_in_use={"p1": 2, "p2": 1}, now=NOW)
    assert stats["totals"] == {"training_runs": 2, "rows": 440, "models": 17, "in_use": 3}
    assert stats["open"] == {"training_runs": 1, "rows": 140, "models": 12, "in_use": 2}
    assert [(p["name"], p["rows"], p["open"]) for p in stats["per_project"]] == \
        [("Beta", 300, False), ("Alpha", 140, True)]
    last = stats["per_week"][-1]
    assert (last["succeeded"], last["failed"]) == (2, 1)
    assert sum(w["succeeded"] for w in stats["per_week"]) == 3
    assert [r["kind"] for r in stats["latest"]] == ["training", "prediction"]


def test_quality_uses_the_configured_metric_and_averages_the_last_three():
    evaluation = {"mcc": 0.2, "accuracy": 0.9, "f1_weighted": 0.8}
    records = [_record("p", days=d, scoring="f1_weighted",
                       evaluation=dict(evaluation, f1_weighted=v))
               for d, v in ((9, 0.5), (6, 0.6), (3, 0.7), (1, 0.8))]
    stats = overview_stats(records, project_names={"p": "P"}, open_project="p",
                           models_in_use={}, now=NOW)
    assert [q["value"] for q in stats["quality"]] == [0.5, 0.6, 0.7, 0.8]
    assert stats["quality_average"] == pytest.approx(0.7) and stats["quality_metric"] == "f1_weighted"
    micro = overview_stats([_record("p", scoring="f1_micro", evaluation=evaluation)],
                           project_names={"p": "P"}, open_project="p", models_in_use={}, now=NOW)
    assert micro["quality"][0]["metric"] == "accuracy"           # micro equals accuracy
    auc = overview_stats([_record("p", scoring="auc", evaluation=evaluation)],
                         project_names={"p": "P"}, open_project="p", models_in_use={}, now=NOW)
    assert auc["quality"][0]["metric"] == "mcc"                  # not kept: MCC instead


def test_without_an_open_project_only_the_totals():
    stats = overview_stats([_record("p", rows=5)], project_names={"p": "P"}, open_project=None,
                           models_in_use={"p": 1}, now=NOW)
    assert stats["totals"]["rows"] == 5 and stats["quality"] == [] and stats["latest"] == []


# --- The charts --------------------------------------------------------------------------

def test_charts_are_svg_with_placeholders_and_escaped_names():
    weeks = [{"week": NOW, "succeeded": 0, "failed": 0}]
    empty = week_bars(weeks, [("succeeded", "chart-ok", "S")], label="Runs", empty="Nothing yet",
                      week_label=lambda w: "v. 47", language="sv")
    assert empty.startswith("<svg") and "Nothing yet" in empty and "<rect" not in empty
    weeks[0].update(succeeded=3, failed=1)
    bars = week_bars(weeks, [("succeeded", "chart-ok", "S"), ("failed", "chart-fail", "F")],
                     label="Runs", empty="-", week_label=lambda w: "v. 47", language="sv")
    assert bars.count("<rect") == 2 and "v. 47" in bars
    named = project_bars([{"name": "<b>x</b>", "rows": 1500, "open": True}], label="Rows",
                         empty="-", language="sv")
    assert "&lt;b&gt;x&lt;/b&gt;" in named and "chart-hl" in named and "1\u00a0500" in named
    line = quality_line([{"value": 0.5, "created_at": NOW}, {"value": 0.7, "created_at": NOW}],
                        0.6, label="Q", empty="-", average_label="Avg",
                        point_label=lambda p: "d", language="sv")
    assert "<polyline" in line and "chart-avg" in line and "0,60" in line


# --- The worker's counts -----------------------------------------------------------------

def test_the_worker_counts_rows_and_models(tmp_path):
    import pandas as pd
    from JBGRunJobStore import RunJobStore
    from JBGRunWorker import StoreProgressLogger
    store = RunJobStore.sqlite(tmp_path / "s.sqlite")
    store.create_tables()
    run = store.create("o", DataSourceKind.CSV, {"spec_version": 1})
    engine = SimpleNamespace(investigate_dataset=lambda *a, **k: True,
                             start_inline_progress=lambda *a: None,
                             update_inline_progress=lambda *a: None)
    observed = StoreProgressLogger(engine, store, run, SimpleNamespace(lost=False))
    observed._inner_checkpoint = lambda: None
    observed.start_inline_progress("f", "Fetching data", 500, "")
    observed.update_inline_progress("f", 480, "")
    assert observed.counts() == {"rows": 480, "models": 0}          # fetched, so far
    observed.investigate_dataset(pd.DataFrame({"a": range(135)}), "a")
    observed.start_inline_progress("m", "Checking & Training models", 40, "")
    observed.update_inline_progress("m", 17, "")
    observed.update_inline_progress("m", 40, "")
    assert observed.counts() == {"rows": 135, "models": 40}
    store.close()


# --- The page ----------------------------------------------------------------------------

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


def test_the_page_shows_both_parts(tmp_path):
    pytest.importorskip("fastapi")
    from JBGIdentity import AuthenticatedPrincipal, AuthenticationMode
    owner = AuthenticatedPrincipal(AuthenticationMode.LOCAL, "developer").principal_key
    with _client(tmp_path) as client:
        ids = []
        for name in ("Alpha", "Beta"):
            location = client.post("/ui/projects", data={"name": name, "source": "csv"},
                                   follow_redirects=False).headers["location"]
            ids.append(re.search(r"selected=([0-9a-f-]{36})", location).group(1))
        store = client.app.state.jbg["store"]
        for project, rows in ((ids[0], 1200), (ids[1], 300)):
            run = store.create(owner, DataSourceKind.CSV, {"spec_version": 1, "project_run": {
                "project_id": project, "kind": "training", "configuration_name": "C"}})
            store.claim(run, "w")
            store.finish(run, "w", RunStatus.SUCCEEDED, result={
                "schema_version": 1, "counts": {"rows": rows, "models": 8}})
        page = client.get("/ui/overview").text                       # no open project
        assert "Alla dina projekt" in page and "varav i det öppna projektet" not in page
        assert "Öppna ett projekt" in page or "Projekt" in page
        assert re.search(r"Bearbetade rader</span>\s*<b class=\"figure-value\">1\u00a0500</b>",
                         page)
        client.post(f"/ui/projects/{ids[0]}/open")
        page = client.get("/ui/overview").text
        assert "varav i det öppna projektet: 1\u00a0200" in page
        assert page.count("<svg class=\"chart\"") == 4
        assert "Senaste körningarna i projektet" in page and "Modellkvalitet per träningskörning" in page
        assert "Inga avslutade träningskörningar med utvärdering ännu." in page
