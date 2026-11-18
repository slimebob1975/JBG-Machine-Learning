"""300e, DN-03 (settled 2026-11-18): the correction factor c measured
out-of-fold, shown beside the in-sample c during the transition (the Dark
Number keeps the in-sample c). Five folds, 3 to 10 repeats with a dynamic stop
(the 90 % interval within +/-10 % of c), the 90 % interval shown, and a
quality state: reliable (within +/-25 %), uncertain (used, flagged) or not
estimable (outside 1-10: undefined)."""
import warnings

import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier

from JBGDarkNumberOutOfFold import (FOLDS, MAX_REPEATS, MIN_REPEATS, _flip, _interval,
                                    estimate)
from test_revision_299n_dn01_baseline import Rule, _data


def test_the_settings():
    assert (FOLDS, MIN_REPEATS, MAX_REPEATS) == (5, 3, 10)


def test_flipping_by_class_size():
    y = np.array(["t"] * 100 + ["a"] * 300 + ["b"] * 100)
    flipped, chosen = _flip(y, "t", 0.2, np.random.default_rng(1))
    assert len(chosen) == 20 and (flipped == "t").sum() == 80
    assert set(flipped[chosen]) <= {"a", "b"}


def test_the_interval_and_the_stop():
    c, low, high = _interval([0.5, 0.5, 0.5])
    assert c == pytest.approx(2.0) and low == pytest.approx(2.0) and high == pytest.approx(2.0)
    c, low, high = _interval([0.4, 0.6, 0.5])
    assert low < c < high


def test_a_robust_model_gives_a_reliable_c_in_range():
    X, y = _data()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = estimate(LogisticRegression(), X, y, "pos", flip_fraction=0.2, random_state=42)
    assert MIN_REPEATS <= result["repeats"] <= MAX_REPEATS
    assert 1.0 <= result["c"] <= 10.0 and result["quality"] in ("reliable", "uncertain")
    assert result["c_low"] <= result["c"] <= result["c_high"]


def test_out_of_fold_c_is_lower_than_in_sample_for_a_memorising_model():
    from JBGDarkNumberCorrectionFactor import DarkNumberCorrectionFactorEstimator
    X, y = _data()
    tree = DecisionTreeClassifier(random_state=0)
    in_sample = DarkNumberCorrectionFactorEstimator(
        estimator=tree, flip_fraction=0.2, n_splits=4, n_repeats=2, n_jobs=1,
        random_state=42, positive_class="pos", sample_size=1.0).fit(X, y)
    assert in_sample.mean_recovery_ == pytest.approx(0.0)          # c infinite in-sample
    oof = estimate(tree, X, y, "pos", flip_fraction=0.2, random_state=42)
    assert oof["recoveries"] and min(oof["recoveries"]) > 0.0     # out-of-fold: found


def test_a_rule_model_is_stable_and_stops_early():
    X, y = _data()
    result = estimate(Rule(), X, y, "pos", flip_fraction=0.2, random_state=1)
    assert MIN_REPEATS <= result["repeats"] < MAX_REPEATS          # stopped early
    assert result["quality"] == "reliable"


def test_the_handler_shows_both_side_by_side():
    import test_dark_number_dense_input as dense
    X, y = dense.dataset()
    models = dense.fitted_models(X, y)
    handler = dense.handler()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        dense.run(handler, X, y, models)
    frame = handler.dark_numbers
    assert {"corr_oof", "corr_oof_low", "corr_oof_high", "corr_oof_quality",
            "dark_number_oof"} <= set(frame.columns)
    names = frame["Model type"].replace("", pd.NA).ffill().astype(str)
    assert set(frame.loc[names.str.startswith("D_cv_test"), "corr_oof_quality"]) == \
        {"not applied"}
    assert list(frame["dark_number"]) == list(handler.dark_numbers["dark_number"])


def test_the_results_tab_names_the_columns_and_qualities():
    from JBGWebUI import _load_catalog, translator
    from JBGWebUIResults import DARK_COLUMNS, OOF_QUALITY, readable_dark_table
    catalog = _load_catalog("sv")
    for key in ("corr_oof", "corr_oof_low", "corr_oof_high", "corr_oof_quality",
                "dark_number_oof"):
        assert DARK_COLUMNS[key] in catalog
    assert all(label in catalog for label in OOF_QUALITY.values())
    detail = {"columns": ["Model type", "corr_oof_quality"],
              "rows": [["D_cv_full - M", "uncertain"], ["D_cv_test - M", "not applied"]]}
    readable_dark_table(detail, translator("sv"), "sv")
    assert [r[1] for r in detail["rows"]] == ["Osäker", "Används inte (testdel)"]
