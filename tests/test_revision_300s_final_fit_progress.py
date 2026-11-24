"""300s (asked 2026-11-23): the Run tab showed nothing during the final training
of the winning pipeline. It now has a bar of its own: 0 or 1 of 1 for an
ordinary fit, and for a grid search the time against the engine's estimate
(agreed 2026-11-23), waiting at 95 % until done. Also: Precision and Recall
with text classes, the QDA test, and .coverage out of the repository."""
import pickle
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

pytest.importorskip("sqlalchemy")

from JBGRunOverview import FINAL_FIT_KINDS, INNER_KINDS, project_run_overview  # noqa: E402
from JBGApplicationContracts import RunStatus  # noqa: E402
from test_revision_297a_inner_progress import (_Logger, _client, _panel, _running,  # noqa: E402
                                               _store)

ROOT = Path(__file__).resolve().parent.parent


def _proxy(tmp_path):
    from JBGRunWorker import StoreProgressLogger
    store, run = _store(tmp_path)
    return StoreProgressLogger(_Logger(), store, run, SimpleNamespace(lost=False)), store, run


def _inner(store, run):
    return [e.message for e in store.progress(run) if e.message.startswith("jbg_inner:")]


# --- The worker's bar -------------------------------------------------------------------

def test_the_new_kinds_are_reviewed_kinds():
    assert FINAL_FIT_KINDS == {"final_fit", "grid_search"} and FINAL_FIT_KINDS <= INNER_KINDS


@pytest.mark.parametrize("estimate", [None, 0, 0.5, float("nan"), float("inf"), "x", -3])
def test_without_a_usable_estimate_the_bar_is_one_step(tmp_path, estimate):
    proxy, store, run = _proxy(tmp_path)
    proxy.begin_final_fit(estimate)
    assert _inner(store, run) == ["jbg_inner:final_fit:0:1"]
    proxy.end_final_fit()
    assert _inner(store, run) == ["jbg_inner:final_fit:1:1"]


def test_a_grid_search_moves_with_the_time_and_waits_before_the_end(tmp_path, monkeypatch):
    import JBGRunWorker
    clock = {"now": 1000.0}
    monkeypatch.setattr(JBGRunWorker.time, "monotonic", lambda: clock["now"])
    proxy, store, run = _proxy(tmp_path)
    proxy.FINAL_FIT_INTERVAL = 0.01
    proxy.begin_final_fit(120.4)
    assert _inner(store, run) == ["jbg_inner:grid_search:0:120"]

    def wait_for(predicate):
        import time as real_time
        for _ in range(500):
            message = _inner(store, run)[-1]
            done, total = map(int, message.split(":")[2:])
            if predicate(done, total):
                return done, total
            real_time.sleep(0.01)
        raise AssertionError(message)
    clock["now"] += 60
    assert wait_for(lambda d, t: d == 60) == (60, 120)
    clock["now"] += 300                                       # past the estimate
    done, total = wait_for(lambda d, t: t > 120)
    assert total == int(360 / 0.95) + 1 and done == int(total * 0.95) < total
    proxy.end_final_fit()
    assert _inner(store, run) == [f"jbg_inner:grid_search:{total}:{total}"]
    assert proxy._final_fit_timer is None


def test_a_new_beginning_replaces_the_one_step_bar(tmp_path):
    proxy, store, run = _proxy(tmp_path)
    proxy.begin_final_fit(None)                     # fit_selected_model
    proxy.begin_final_fit(240)                      # then the grid search's estimate
    assert _inner(store, run) == ["jbg_inner:grid_search:0:240"]
    proxy.end_final_fit()
    assert _inner(store, run) == ["jbg_inner:grid_search:240:240"]


def test_ending_without_a_beginning_records_nothing(tmp_path):
    proxy, store, run = _proxy(tmp_path)
    proxy.end_final_fit()
    assert _inner(store, run) == []


# --- The engine -------------------------------------------------------------------------

def _context(params, logger):
    model = SimpleNamespace(algorithm=SimpleNamespace(search_params=SimpleNamespace(
        parameters=params)), pipeline=Mock())
    model.get_name = Mock(return_value="PRE-LRN")
    context = SimpleNamespace(handler=SimpleNamespace(logger=logger),
                              train_picked_model=Mock(return_value="fitted"),
                              model_parameter_grid_search=Mock(return_value=(Mock(), {})),
                              _export_final_search_results=Mock())
    return context, model, SimpleNamespace(X_train=object(), Y_train=object())


def test_the_final_fit_begins_and_ends_the_bar():
    from JBGFinalFitService import fit_selected_model
    logger = Mock(reports_final_fit=True)
    context, model, dh = _context({}, logger)
    fit_selected_model(context, model, dh, 3, "out.csv")
    names = [c[0] for c in logger.method_calls if c[0] in ("begin_final_fit", "end_final_fit")]
    assert names == ["begin_final_fit", "end_final_fit"]
    logger.begin_final_fit.assert_called_once_with(None)


def test_the_bar_ends_also_when_the_fit_fails():
    from JBGFinalFitService import fit_selected_model
    logger = Mock(reports_final_fit=True)
    context, model, dh = _context({"C": [1]}, logger)
    context.model_parameter_grid_search.side_effect = RuntimeError("unexpected")
    with pytest.raises(RuntimeError):
        fit_selected_model(context, model, dh, 3, "out.csv")
    logger.end_final_fit.assert_called_once_with()


def test_a_logger_without_the_bar_is_left_alone():
    # Voilà's logger has no reports_final_fit; a Mock's attribute is not True.
    from JBGFinalFitService import fit_selected_model
    for logger in (Mock(), SimpleNamespace(print_progress=Mock(), print_info=Mock(),
                                           print_code=Mock())):
        context, model, dh = _context({}, logger)
        fit_selected_model(context, model, dh, 3, "out.csv")
        assert not getattr(logger, "begin_final_fit", Mock()).called


def test_the_grid_search_passes_its_estimate():
    from test_final_search import data, handler, pipe
    mh, (X, y) = handler(), data()
    mh.handler.logger.reports_final_fit = True
    mh._report_grid_search_estimate = Mock(return_value=SimpleNamespace(seconds=42.0))
    try:
        mh.model_parameter_grid_search(pipe(n_estimators=5), {"ETC__max_depth": [None, 3]}, 3, X, y)
    except Exception:
        pass             # the estimate stand-in may not satisfy the time comparison
    mh.handler.logger.begin_final_fit.assert_called_once_with(42.0)


# --- The panel --------------------------------------------------------------------------

def test_the_panel_shows_the_grid_search_in_minutes(tmp_path):
    with _client(tmp_path) as client:
        store, run = _running(client)
        store.record_inner_progress(run, "grid_search", 125, 240)
        page = client.get(f"/ui/run?run={run.key}").text
        store.record_inner_progress(run, "grid_search", 30, 240)
        early = client.get(f"/ui/run?run={run.key}").text
        store.record_inner_progress(run, "final_fit", 0, 1)
        ordinary = client.get(f"/ui/run?run={run.key}").text
    panel = _panel(page)
    assert "<span data-inner-label>Parametersökning för vald pipeline, uppskattad tid</span>" in panel
    assert "<span data-inner-count>2 min av cirka 4 min</span>" in panel
    assert 'data-inner-timed="grid_search"' in panel and 'data-inner-about="cirka"' in panel
    assert "<span data-inner-count>under 1 min av cirka 4 min</span>" in _panel(early)
    assert "<span data-inner-label>Slutträning av vald pipeline</span>" in _panel(ordinary)
    assert "<span data-inner-count>0 av 1</span>" in _panel(ordinary)


def test_the_overview_carries_the_new_kinds():
    class Event:
        def __init__(self, message):
            self.message, self.percent = message, None
    events = [Event("jbg_stage:train_model"), Event("jbg_inner:grid_search:10:240")]
    stage = project_run_overview("r", RunStatus.RUNNING, events)["stage"]
    assert stage["inner"] == {"kind": "grid_search", "done": 10, "total": 240}


def test_the_script_formats_the_timed_kind():
    script = (ROOT / "src" / "web" / "static" / "jbg.js").read_text(encoding="utf-8")
    assert 'inner.kind === box.getAttribute("data-inner-timed")' in script
    assert 'Math.round(s / 60) + " min"' in script


# --- Precision and Recall with text classes ---------------------------------------------

@pytest.mark.parametrize("name", ["precision_micro", "precision_macro", "precision_weighted",
                                  "recall_micro", "recall_macro", "recall_weighted"])
def test_precision_and_recall_score_text_classes(name):
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import StratifiedKFold, cross_val_score
    from JBGMeta import ScoreMetric
    rng = np.random.default_rng(3)
    X = rng.normal(size=(120, 3))
    numbers = (X[:, 0] + rng.normal(scale=0.5, size=120) > 0.8).astype(int)
    text = np.where(numbers == 1, "Inkorrekt", "Korrekt")
    metric = ScoreMetric[name]
    scores = [cross_val_score(LogisticRegression(), X, labels, cv=StratifiedKFold(3),
                              scoring=metric.get_parametrized_scorer(), error_score="raise").mean()
              for labels in (text, numbers)]
    assert scores[0] == pytest.approx(scores[1])


def test_the_stored_metric_values_are_unchanged():
    from JBGMeta import ScoreMetric
    assert ScoreMetric.precision_macro.value["kwargs"] == {"average": "macro"}
    assert ScoreMetric.recall_weighted.value["kwargs"] == {"average": "weighted"}
    for metric in ScoreMetric:
        assert pickle.loads(pickle.dumps(metric)) is metric


# --- A new dataset's name (asked 2026-11-23) ---------------------------------------------

def test_the_name_fields_start_from_the_file_or_table():
    page = (ROOT / "src" / "web" / "templates" / "dataset.html").read_text(encoding="utf-8")
    assert '<input id="csv-name" name="name" required maxlength="200" data-name-from="#csv-file">' \
        in page
    assert 'data-name-from="#sql-table"' in page
    assert "value=\"{{ table_choice.tables[0].split('.')[-1][:200] }}\"" in page
    script = (ROOT / "src" / "web" / "static" / "jbg.js").read_text(encoding="utf-8")
    assert 'file.name.replace(/\\.csv$/i, "")' in script
    assert 'value.slice(value.lastIndexOf(".") + 1)' in script
    assert 'if (input.value !== "" && input.value !== filled) { return; }' in script
    assert 'querySelectorAll("input[data-name-from]").forEach(wireDefaultName)' in script


def test_the_sql_name_starts_as_the_first_tables_name():
    from jinja2 import Environment
    template = Environment().from_string(
        "{{ table_choice.tables[0].split('.')[-1][:200] }}")
    assert template.render(table_choice={"tables": ["dbo.Ärenden", "dbo.B"]}) == "Ärenden"
    assert template.render(table_choice={"tables": ["Utan_schema"]}) == "Utan_schema"


# --- Housekeeping -----------------------------------------------------------------------

def test_coverage_data_is_ignored():
    lines = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".coverage" in lines and ".coverage.*" in lines
