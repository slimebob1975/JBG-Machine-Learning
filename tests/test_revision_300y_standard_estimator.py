"""300y (asked 2026-11-24): when c cannot be used for a target class (above the
upper bound or not estimable), the Dark Numbers computation is repeated with
logistic regression in place of the pipeline's algorithm. Only the algorithm
is replaced (agreed 2026-11-24). On by default, with a checkbox in the
Mörkertal section, and the user is always told."""
import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression

from test_dark_number_dense_input import dataset, fitted_models, handler

ROOT = Path(__file__).resolve().parent.parent


def _handler(c_max=1.05, enabled=True):
    ph = handler()
    ph.handler.config.mode = SimpleNamespace(
        dark_number_c_max=c_max, dark_number_c_warning=min(c_max, 10.0),
        dark_number_flip_repeats=1, dark_number_standard_estimator=enabled)
    ph.handler.config.get_max_iterations = lambda: 2000
    calls = []
    original = ph.get_dark_numbers

    def counting(**kwargs):
        calls.append(list(kwargs["models"]))
        return original(**kwargs)
    ph.get_dark_numbers = counting
    return ph, calls


def _run(ph, models):
    X, y = dataset()
    ph.get_dark_numbers_with_standard_estimator(
        X=X, Y=y, models=models, model_names=["Cross", "Retrained"], target_class="1",
        X_validation=X.iloc[120:], Y_validation=y.iloc[120:],
        X_cv_training=X.iloc[:120], Y_cv_training=y.iloc[:120], type="all")


def test_an_unusable_c_repeats_the_computation_with_logistic_regression():
    X, y = dataset()
    models = fitted_models(X, y)
    ph, calls = _handler(c_max=1.05)
    _run(ph, models)
    assert len(calls) == 2
    for copy, model in zip(calls[1], models):
        assert [name for name, _ in copy.steps] == [name for name, _ in model.steps]
        assert isinstance(copy.steps[-1][1], LogisticRegression)       # only the algorithm
        assert type(copy.steps[0][1]) is type(model.steps[0][1])       # the rest is kept
        assert hasattr(copy.steps[-1][1], "coef_")                     # fitted
        assert type(model.steps[-1][1]).__name__ == "HistGradientBoostingClassifier"
    standard = ph.__dict__["dark_number_used"]["standard_estimator"]
    assert standard["used"] is True and standard["targets"] == ["1"]
    assert standard["replaced"] == ["HistGradientBoostingClassifier"]
    assert standard["algorithm"] == "Logistic Regression"
    assert any("Logistic Regression in place of the pipeline's algorithm" in w
               for w in ph.handler.logger.warnings)


def test_a_usable_c_needs_no_repeat():
    X, y = dataset()
    ph, calls = _handler(c_max=100.0)
    _run(ph, fitted_models(X, y))
    assert len(calls) == 1
    assert "standard_estimator" not in ph.__dict__["dark_number_used"]


def test_switched_off_it_keeps_the_undefined_estimates():
    X, y = dataset()
    ph, calls = _handler(c_max=1.05, enabled=False)
    _run(ph, fitted_models(X, y))
    assert len(calls) == 1
    assert ph._targets_without_usable_correction() == ["1"]


def test_a_failing_fit_keeps_the_pipelines_own_results(monkeypatch):
    X, y = dataset()
    ph, calls = _handler(c_max=1.05, enabled=False)
    _run(ph, fitted_models(X, y))                      # the pipeline's own results
    first = ph.dark_numbers.copy()
    ph, calls = _handler(c_max=1.05)

    def broken(model, X, Y):
        raise ValueError("no fit")
    monkeypatch.setattr(ph, "_fit_standard_copy", broken)
    _run(ph, fitted_models(X, y))
    assert len(calls) == 1
    pd.testing.assert_frame_equal(ph.dark_numbers, first)
    standard = ph.__dict__["dark_number_used"]["standard_estimator"]
    assert standard == {"used": False, "failed": "ValueError", "targets": ["1"]}


# --- The setting, the record and the view -----------------------------------------------

def test_the_setting_is_on_by_default():
    from Config import Config
    assert Config.Mode().dark_number_standard_estimator is True
    assert Config.LATER_KEYS["mode"]["dark_number_standard_estimator"] is True
    with pytest.raises(TypeError):
        Config.Mode(dark_number_standard_estimator="yes").validate()
    from JBGConfigSchema import configuration_schema
    from JBGConfigurationService import _server_template
    from JBGWebUI import translator
    fields = {f["key"]: f for f in configuration_schema("csv", translator("sv"),
                                                        _server_template())["fields"]}
    field = fields["mode.dark_number_standard_estimator"]
    assert field["group"] == "dark_numbers" and field["kind"] == "boolean"
    assert field["label"] == "Använd logistisk regression när c inte kan användas"
    assert not field.get("advanced")


def test_the_record_carries_it():
    from JBGDarkNumberRecord import parameters
    from test_revision_299x_dark_number_record import CONFIG
    used = {"standard_estimator": {"used": True, "targets": ["1"], "replaced": ["X"],
                                   "algorithm": "Logistic Regression", "still_undefined": []}}
    p = parameters(CONFIG, used)
    assert p["standard_estimator"]["used"] is True and p["standard_estimator_enabled"] is True
    assert parameters(CONFIG, {})["standard_estimator"] == {"used": False}


def test_the_view_always_says_so(tmp_path):
    from JBGDarkNumberRecord import build
    from test_revision_299b_csv_reclassification import _client, _setting
    from test_revision_299x_dark_number_record import CALCULATIONS, CONFIG
    record = build(CONFIG, pd.DataFrame(), {"random_state": 42})
    record["parameters"]["standard_estimator"] = {
        "used": True, "targets": ["Inkorrekt"], "replaced": ["VotingClassifier"],
        "algorithm": "Logistic Regression", "still_undefined": ["Inkorrekt"]}
    with _client(tmp_path) as client:
        s = _setting(client, tmp_path)
        csvs = s.folder / "output" / "csvs"
        (csvs / "dark_numbers_r__train.csv").write_text(CALCULATIONS, encoding="utf-8")
        (csvs / "dark_numbers_r__train.json").write_text(json.dumps(record), encoding="utf-8")
        used = client.get(f"/ui/results?run={s.run}&view=dark_numbers").text
        record["parameters"]["standard_estimator"] = {"used": False, "failed": "ValueError"}
        (csvs / "dark_numbers_r__train.json").write_text(json.dumps(record), encoding="utf-8")
        failed = client.get(f"/ui/results?run={s.run}&view=dark_numbers").text
        record["parameters"]["standard_estimator"] = {"used": False}
        (csvs / "dark_numbers_r__train.json").write_text(json.dumps(record), encoding="utf-8")
        quiet = client.get(f"/ui/results?run={s.run}&view=dark_numbers").text
    assert "Mörkertalet är beräknat med logistisk regression i stället för pipelinens algoritm" in used
    assert "Målklasser: <b>Inkorrekt</b>" in used and "Ersatt algoritm: <b>VotingClassifier</b>" in used
    assert "c kunde inte heller användas med logistisk regression för: <b>Inkorrekt</b>" in used
    assert "Logistisk regression kunde inte ersätta pipelinens algoritm" in failed
    assert "logistisk regression" not in quiet.lower().replace(
        "använd logistisk regression när c inte kan användas", "")


def test_the_task_runner_uses_it_and_the_guides_describe_it():
    runner = (ROOT / "src" / "JBGTaskRunner.py").read_text(encoding="utf-8")
    assert 'compute = getattr(self.ph, "get_dark_numbers_with_standard_estimator",' in runner
    from JBGHandler import PredictionsHandler                # so the real runs use it
    assert callable(getattr(PredictionsHandler, "get_dark_numbers_with_standard_estimator"))
    sv = (ROOT / "docs" / "user_guide.sv.md").read_text(encoding="utf-8")
    en = (ROOT / "docs" / "user_guide.en.md").read_text(encoding="utf-8")
    assert "**Logistisk regression när c inte kan användas.**" in sv
    assert "**Logistic regression when c cannot be used.**" in en
