"""299n, DN-01 (agreed 2026-11-16): the original JBG Dark Number method (v1)
frozen as it is implemented, on synthetic data only. These are
characterisation tests: they pin current behaviour, including the findings
F1-F9 of docs/dark_numbers/DN-01_method_contract.md, which are not fixed here.
A revision that changes any of these numbers must say so and update the
contract."""
import warnings

import numpy as np
import pandas as pd
import pytest
from sklearn.base import BaseEstimator, ClassifierMixin

from JBGDarkNumberCorrectionFactor import DarkNumberCorrectionFactorEstimator, evaluate_split
from JBGDarkNumbers import DarkNumberCalculator

REAL = pd.Series(["a", "a", "b", "b", "b", "c", "a", "b"])
PREDICTED = pd.Series(["a", "b", "b", "b", "a", "c", "a", "c"])
CERTAINTY = pd.Series([0.9, 0.6, 0.8, 0.7, 0.55, 0.95, 0.85, 0.5])
CORRS = {"a": 2.0, "b": 1.5, "c": 1.0}

# (type, target) -> (alphas, D), computed at 299m.
EXPECTED = {
    ("base", "a"): (1.0, 0.5333333333333333),
    ("base", "b"): (1.0, 0.5625),
    ("base", "c"): (1.0, 0.1428571428571429),
    ("single_alpha", "a"): (0.575, 0.3066666666666666),
    ("single_alpha", "b"): (0.55, 0.309375),
    ("single_alpha", "c"): (0.5, 0.07142857142857145),
    # 299u, JBG v1.2: alpha_FN weighs the misses only, 1 + alpha_FN (1 - TP_r).
    # At 299m: a 0.176, b 0.1771875 (c unchanged: no misses' weight to move).
    ("separated_alpha", "a"): ([0.55, 0.6], 0.26399999999999996),
    ("separated_alpha", "b"): ([0.6, 0.525], 0.28406249999999994),
    ("separated_alpha", "c"): ([0.5, 1.0], 0.07142857142857145),
    ("non_linear", "a"): (1.0, 0.16148853579008574),
    ("non_linear", "b"): (1.0, 0.1654554995061972),
    ("non_linear", "c"): (1.0, 0.05008574840700353),
    ("non_linear_alpha", "a"): (0.575, 0.0928559080792993),
    ("non_linear_alpha", "b"): (0.55, 0.09100052472840846),
    ("non_linear_alpha", "c"): (0.5, 0.025042874203501764),
}


class Rule(BaseEstimator, ClassifierMixin):
    """A stand-in model whose predictions do not depend on the labels or on a
    library's fitting, so the flip mechanics can be pinned exactly."""

    def fit(self, X, y):
        self.classes_ = np.unique(y)
        return self

    def predict(self, X):
        return np.where(np.asarray(X)[:, 0] > 0.75, "pos", "neg")


def _data():
    rng = np.random.default_rng(7)
    y = np.where(rng.random(400) < 0.2, "pos", "neg")
    X = np.c_[rng.normal(size=400) + (y == "pos") * 1.5, rng.normal(size=400)]
    return X, y


def _estimator(model, target):
    return DarkNumberCorrectionFactorEstimator(
        estimator=model, flip_fraction=0.1, n_splits=4, n_repeats=2, n_jobs=1,
        predict_mode="predict", random_state=42, positive_class=target, sample_size=1.0)


# --- Formulas ----------------------------------------------------------------------------

def test_the_five_formula_branches():
    found = DarkNumberCalculator().compute_dark_numbers(REAL, PREDICTED, CERTAINTY, type="all",
                                                        corrs=CORRS)
    assert len(found) == len(EXPECTED)
    for row in found.to_dict("records"):
        alphas, value = EXPECTED[(row["type"], row["target"])]
        got = [float(a) for a in row["alphas"]] if isinstance(row["alphas"], list) \
            else float(row["alphas"])
        assert got == pytest.approx(alphas) and row["dark_number"] == pytest.approx(value)
        assert row["corr"] == CORRS[row["target"]]


def test_f1_undefined_rates_make_the_dark_number_undefined():
    """299o, JBG v1.1 (settled 2026-11-16): an undefined rate gives D = -1.
    At 299m: 8/3 (with 1 - TN_r = 2), and a complex number in the non-linear form."""
    calculator = DarkNumberCalculator()
    assert calculator.compute_posneg_rates(0, 0, 1, 1) == (0.5, -1)
    assert calculator.compute_dark_number(pd.Series([1, 1, 1]), pd.Series([1, 0, 1])) == -1.0
    _, value = calculator.compute_dark_number_non_linear(
        pd.Series([0, 0]), pd.Series([0, 1]), pd.Series([0.6, 0.7]), root_degree=3)
    assert value == -1.0


def test_f2_a_scope_with_one_label_is_undefined():
    """299o, JBG v1.1: a one-label scope has an undefined rate (D = -1). At 299m: raised."""
    assert DarkNumberCalculator().compute_dark_number(pd.Series([0, 0, 0]),
                                                      pd.Series([0, 0, 0])) == -1.0


def test_f7_alpha_is_the_certainty_of_the_predicted_label():
    # One FP (true b, predicted a: certainty 0.55) and one FN for target a
    # (true a, predicted b: certainty 0.6), as the separated alphas above.
    alphas, _ = EXPECTED[("separated_alpha", "a")]
    assert alphas == [CERTAINTY[4], CERTAINTY[1]]


# --- The flip test -----------------------------------------------------------------------

def test_the_flip_test_end_to_end_with_a_rule_model():
    X, y = _data()
    pos = _estimator(Rule(), "pos").fit(X, y)
    assert pos.recovery_results_ == pytest.approx(
        [5 / 6, 5 / 6, 0.5, 5 / 6, 5 / 6, 1.0, 1.0, 1.0])
    assert pos.correction_factor_ == pytest.approx(1.170731707317073)
    neg = _estimator(Rule(), "neg").fit(X, y)
    assert neg.mean_recovery_ == pytest.approx(0.7934782608695652)
    assert neg.correction_factor_ == pytest.approx(1.2602739726027399)
    assert pos.correction_status_ == neg.correction_status_ == "estimated"


def test_the_flip_test_with_logistic_regression_stays_in_range():
    from sklearn.linear_model import LogisticRegression
    X, y = _data()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        minority = _estimator(LogisticRegression(), "pos").fit(X, y)
        majority = _estimator(LogisticRegression(), "neg").fit(X, y)
    assert 2.0 <= minority.correction_factor_ <= 3.5          # 2.67 at 299m
    assert 1.0 <= majority.correction_factor_ <= 1.25         # 1.10 at 299m


def test_f3_a_fold_without_flips_is_not_measured():
    """299p, JBG v1.1 (settled 2026-11-16): None, left out. At 299m: 0.0."""
    y = np.array(["neg"] * 95 + ["pos"] * 5)
    X = np.c_[np.arange(100.0), np.zeros(100)]
    assert evaluate_split(Rule(), X, y, np.arange(100), 0, 0.1, "pos", "predict", 1) is None


def test_f4_recovery_is_measured_on_the_rows_the_clone_was_fitted_on():
    seen = {}

    class Recorder(Rule):
        def fit(self, X, y):
            seen["fit"] = {tuple(row) for row in np.asarray(X)}
            return super().fit(X, y)

        def predict(self, X):
            seen["predict"] = {tuple(row) for row in np.asarray(X)}
            return super().predict(X)
    X, y = _data()
    evaluate_split(Recorder(), X, y, np.arange(300), 0, 0.1, "pos", "predict", 1)
    assert seen["predict"] <= seen["fit"]


def test_f5_flipped_rows_go_to_other_classes_by_size():
    """299r, JBG v1.1 (settled 2026-11-16): a random other class by size.
    At 299m every flipped row went to the first other class ("a": 34, "c": 30)."""
    labels = {}

    class Recorder(Rule):
        def fit(self, X, y):
            labels["y"] = np.asarray(y)
            return super().fit(X, y)
    y = np.array(["b"] * 40 + ["a"] * 30 + ["c"] * 30)
    X = np.c_[np.arange(100.0), np.zeros(100)]
    evaluate_split(Recorder(), X, y, np.arange(100), 0, 0.1, "b", "predict", 1)
    assert (labels["y"] == "b").sum() == 36
    assert (labels["y"] == "a").sum() > 30 and (labels["y"] == "c").sum() > 30


def test_f6_folds_and_repeats_follow_the_cpu_count():
    """The helper still chooses by the CPU count; since 299s (JBG v1.1) the flip
    test no longer uses it (fixed 4 x 2, see test_revision_299s)."""
    from JBGHandler import PredictionsHandler
    choose = PredictionsHandler._auto_n_splits_and_repeats
    chosen = {cores: choose(None, n_jobs_desired=cores, min_n_splits=4, min_n_repeats=2,
                            max_multiplier=3) for cores in (4, 6, 8, 12)}
    assert chosen == {4: (4, 2), 6: (4, 3), 8: (4, 2), 12: (4, 3)}
