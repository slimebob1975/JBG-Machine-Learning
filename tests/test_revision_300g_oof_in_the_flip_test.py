"""300g (2026-11-19): the out-of-fold c is measured inside the existing flip
test, at no extra fit. 300e ran its own 15-50 fits one after another, which
took many hours on large data. Each fold's copy, trained on 75 % of the rows
with some target rows relabelled, also predicts the fold's unseen target rows;
the share predicted as the target is the out-of-fold recovery. The flip test
also shows its progress (and checks for cancelling) as each fold finishes."""
import warnings
from types import SimpleNamespace

import numpy as np
import pytest
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier

from JBGDarkNumberCorrectionFactor import DarkNumberCorrectionFactorEstimator, evaluate_split
from test_revision_299n_dn01_baseline import Rule, _data


def _estimator(model, **extra):
    return DarkNumberCorrectionFactorEstimator(
        estimator=model, flip_fraction=0.2, n_splits=4, n_repeats=2, n_jobs=1,
        random_state=42, positive_class="pos", sample_size=1.0, **extra)


def test_a_fold_returns_the_out_of_fold_recovery_from_the_same_fit():
    X, y = _data()
    fits = []

    class Counting(Rule):
        def fit(self, X, y):
            fits.append(1)
            return super().fit(X, y)
    train, test = np.arange(300), np.arange(300, 400)
    result = evaluate_split(Counting(), X, y, train, 0, 0.2, "pos", "predict", 1, True,
                            "PIPELINE", test)
    assert set(result) == {"recovery", "train_fit", "sampling", "oof"} and len(fits) == 1
    unseen = test[y[test] == "pos"]
    expected = np.mean(Rule().fit(X, y).predict(X[unseen]) == "pos")
    assert result["oof"] == pytest.approx(expected)


def test_the_estimator_collects_eight_values_with_no_extra_fits():
    X, y = _data()
    fits = []

    class Counting(Rule):
        def fit(self, X, y):
            fits.append(1)
            return super().fit(X, y)
    fitted = _estimator(Counting()).fit(X, y)
    assert len(fitted.oof_recoveries_) == 8 and len(fits) == 8      # 4 folds x 2 repeats


def test_the_in_sample_c_is_unchanged():
    X, y = _data()
    fitted = DarkNumberCorrectionFactorEstimator(
        estimator=Rule(), flip_fraction=0.1, n_splits=4, n_repeats=2, n_jobs=1,
        random_state=42, positive_class="pos", sample_size=1.0).fit(X, y)
    assert fitted.correction_factor_ == pytest.approx(1.170731707317073)   # 299n's pin


def test_a_memorising_model_recovers_out_of_fold():
    X, y = _data()
    tree = _estimator(DecisionTreeClassifier(random_state=0)).fit(X, y)
    assert tree.mean_recovery_ == pytest.approx(0.0)                    # in-sample: c infinite
    assert np.mean(tree.oof_recoveries_) > 0.3                         # out-of-fold: found


def test_progress_moves_with_each_fold():
    X, y = _data()
    calls = []
    logger = SimpleNamespace(
        reports_correction_progress=True,
        start_inline_progress=lambda key, text, total, tip: calls.append(("start", total)),
        update_inline_progress=lambda key, done, text: calls.append(("update", done)),
        end_inline_progress=lambda key, set_100=True: calls.append(("end",)),
        print_info=lambda *a, **k: None)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _estimator(LogisticRegression(), logger=logger).fit(X, y)
    assert calls[0] == ("start", 8) and calls[-1] == ("end",)
    assert [c[1] for c in calls if c[0] == "update"] == list(range(1, 9))


def test_the_worker_logger_reports_and_names_the_bar():
    from JBGRunOverview import INNER_KINDS
    from JBGRunWorker import StoreProgressLogger
    assert StoreProgressLogger.reports_correction_progress is True
    assert "correction_folds" in INNER_KINDS
