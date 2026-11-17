"""299q, JBG v1.1 (DN-01 F4, settled 2026-11-16, option C): recovery in the
flip test is measured on the rows the correction model was fitted on. A model
that memorises its training rows also reproduces the flipped (wrong) labels,
so recovery is understated and c overstated. The flip test now also measures
the fitted copy's fit to its unflipped training rows (no extra fitting); at
0.99 or more a warning says that c and the Dark Number may be too high. No
number changes. Out-of-fold recovery is the v2 definition (DN-03)."""
import warnings

import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier

from JBGDarkNumberCorrectionFactor import DarkNumberCorrectionFactorEstimator, evaluate_split
from JBGDarkNumberReporting import MEMORISATION_THRESHOLD, build_dark_number_intervals
from JBGDarkNumbers import DarkNumberCalculator
from test_revision_299n_dn01_baseline import Rule, _data


def test_the_threshold():
    assert DarkNumberCalculator.MEMORISATION_THRESHOLD == MEMORISATION_THRESHOLD == 0.99


def test_the_flip_test_also_measures_the_training_fit():
    X, y = _data()
    plain = evaluate_split(Rule(), X, y, np.arange(300), 0, 0.1, "pos", "predict", 1)
    recovery, fit = evaluate_split(Rule(), X, y, np.arange(300), 0, 0.1, "pos", "predict", 1,
                                   return_fit=True)
    assert recovery == plain and 0.0 < fit < 1.0              # the rule does not memorise
    few = np.array(["neg"] * 95 + ["pos"] * 5)
    assert evaluate_split(Rule(), np.c_[np.arange(100.0), np.zeros(100)], few, np.arange(100), 0,
                          0.1, "pos", "predict", 1, return_fit=True) == (None, None)


def test_a_memorising_model_fits_everything_and_recovers_nothing():
    X, y = _data()
    tree = DarkNumberCorrectionFactorEstimator(
        estimator=DecisionTreeClassifier(random_state=0), flip_fraction=0.2, n_splits=4,
        n_repeats=2, n_jobs=1, predict_mode="predict", random_state=42,
        positive_class="pos", sample_size=1.0).fit(X, y)
    assert tree.train_fit_ == pytest.approx(1.0) and tree.mean_recovery_ == pytest.approx(0.0)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        linear = DarkNumberCorrectionFactorEstimator(
            estimator=LogisticRegression(), flip_fraction=0.2, n_splits=4, n_repeats=2,
            n_jobs=1, predict_mode="predict", random_state=42, positive_class="pos",
            sample_size=1.0).fit(X, y)
    assert linear.train_fit_ < MEMORISATION_THRESHOLD and linear.mean_recovery_ > 0.2


def test_plain_fold_results_leave_the_fit_unknown():
    X, y = _data()
    estimator = DarkNumberCorrectionFactorEstimator(
        estimator=Rule(), flip_fraction=0.1, n_splits=4, n_repeats=2, n_jobs=1,
        predict_mode="predict", random_state=42, positive_class="pos", sample_size=1.0)
    estimator._run_parallel = lambda tasks: [0.8] * 8
    assert estimator.fit(X, y).train_fit_ is None


def test_the_handler_reports_the_fit_beside_c():
    import test_dark_number_dense_input as dense
    X, y = dense.dataset()
    models = dense.fitted_models(X, y)
    handler = dense.handler()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        dense.run(handler, X, y, models)
    frame = handler.dark_numbers
    assert "corr_train_fit" in frame.columns
    fits = [v for v in frame["corr_train_fit"] if v is not None and v == v]
    assert fits and all(0.0 <= v <= 1.0 for v in fits)
    assert list(frame.columns).index("corr_train_fit") == list(frame.columns).index("corr_source") + 1


def test_the_summary_flags_a_memorising_correction_model():
    rows = pd.DataFrame([
        {"Model type": "D_cv_test - T", "type": "separated_alpha", "target": "a",
         "corr": 4.0, "corr_model": "T", "corr_source": "direct", "corr_train_fit": 0.995,
         "dark_number": 0.2},
        {"Model type": "D_cv_full - L", "type": "separated_alpha", "target": "a",
         "corr": 1.2, "corr_model": "L", "corr_source": "direct", "corr_train_fit": 0.9,
         "dark_number": 0.3},
    ])
    points = {p["label"]: p for p in build_dark_number_intervals(rows)[0]["points"]}
    assert points["D_cv_test"]["memorises"] is True and points["D_cv_full"]["memorises"] is False
    assert points["D_cv_test"]["value"] == 0.2                   # the number is unchanged


def test_the_results_tab_shows_the_fit_and_the_warning():
    from JBGWebUI import WEB, _load_catalog, translator
    from JBGWebUIResults import readable_dark_table
    detail = {"columns": ["Model type", "corr_train_fit"], "rows": [["D_cv_test - T", "0.995"]]}
    readable_dark_table(detail, translator("sv"), "sv")
    assert detail["rows"][0][1] == "99,5 %"
    template = (WEB / "templates" / "results.html").read_text(encoding="utf-8")
    assert 'selectattr("memorises")' in template
    assert "Training fit (correction model)" in _load_catalog("sv")
