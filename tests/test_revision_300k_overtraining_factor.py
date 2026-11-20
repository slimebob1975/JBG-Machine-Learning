"""300k (agreed 2026-11-19, in the validation study only): the overtraining
factor c_over = c / c_unseen = r_unseen / r_in, per fold of the flip test,
averaged, at least 1. The model's ordinary misses and the effect of the
relabelled labels cancel in the ratio, so only memorisation is left; the
misses are already in (1 + alpha_FN (1 - TP_r)). The study computes and judges
D with c_over beside D (1.2); the GUI and ordinary runs are unchanged."""
import math
import warnings

import pandas as pd
import pytest

from JBGDarkNumberOutOfFold import overtraining_factor
from test_revision_299n_dn01_baseline import Rule, _data


def test_the_factor():
    same = overtraining_factor([(0.6, 0.6)] * 8)
    assert same["c"] == pytest.approx(1.0) and same["quality"] == "reliable"
    more = overtraining_factor([(0.3, 0.6)] * 8)
    assert more["c"] == pytest.approx(2.0)
    below = overtraining_factor([(0.7, 0.6)] * 8)                      # not below 1
    assert below["c"] == 1.0 and below["c_low"] == 1.0
    memorised = overtraining_factor([(0.0, 0.6), (0.3, 0.6)])
    assert math.isinf(memorised["c"]) and memorised["quality"] == "not_estimable"
    assert overtraining_factor([])["quality"] == "not_estimable"


def test_the_flip_test_keeps_the_pairs():
    from JBGDarkNumberCorrectionFactor import DarkNumberCorrectionFactorEstimator
    X, y = _data()
    fitted = DarkNumberCorrectionFactorEstimator(
        estimator=Rule(), flip_fraction=0.2, n_splits=4, n_repeats=2, n_jobs=1,
        random_state=42, positive_class="pos", sample_size=1.0).fit(X, y)
    assert len(fitted.fold_pairs_) == 8
    assert [r for r, _ in fitted.fold_pairs_] == fitted.recovery_results_
    assert [u for _, u in fitted.fold_pairs_] == fitted.oof_recoveries_


def test_since_1_3_the_handler_uses_the_factor_as_c():
    """300l: JBG 1.3, c = c_in / c_unseen in every run (not only the study)."""
    import test_dark_number_dense_input as dense
    from JBGDarkNumbers import DarkNumberCalculator
    X, y = dense.dataset()
    models = dense.fitted_models(X, y)
    handler = dense.handler()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        dense.run(handler, X, y, models)
    frame = handler.dark_numbers
    names = frame["Model type"].replace("", pd.NA).ffill().astype(str)
    in_sample = frame[~names.str.startswith("D_cv_test")]
    for _, row in in_sample.iterrows():
        if row["corr"] != DarkNumberCalculator.UNDEFINED and row["corr_in_sample"] is not None:
            assert row["corr"] <= row["corr_in_sample"] + 1e-9


def test_the_study_records_cs_parts():
    from JBGDarkNumberStudy import Cell, run_once
    rows = pd.DataFrame(run_once(Cell(0.10, 0.5, "strong", rows=1200), 3))
    assert {"c_in_sample", "c_unseen"} <= set(rows.columns)
    in_sample = rows[(rows["estimate"] != "D_cv_test") & (rows["c"] > 0)]
    assert (in_sample["c"] <= in_sample["c_in_sample"] + 1e-9).all()
