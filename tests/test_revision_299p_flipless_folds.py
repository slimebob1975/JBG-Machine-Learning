"""299p, JBG v1.1 (DN-01 F3, settled 2026-11-16): a fold of the flip test with
no flipped rows measures nothing. It counted as recovery 0, pulling the mean
down and c up; it is now left out, and at least half of all folds must have
flipped rows, or c cannot be estimated (c = -1 and D = -1 by v1.1)."""
import numpy as np
import pytest

from JBGDarkNumberCorrectionFactor import (MIN_MEASURED_FOLD_SHARE,
                                           DarkNumberCorrectionFactorEstimator)
from test_revision_299n_dn01_baseline import Rule, _data


def _fit_with(results):
    X, y = _data()
    estimator = DarkNumberCorrectionFactorEstimator(
        estimator=Rule(), flip_fraction=0.1, n_splits=4, n_repeats=2, n_jobs=1,
        predict_mode="predict", random_state=42, positive_class="pos", sample_size=1.0)
    estimator._run_parallel = lambda tasks: list(results)
    return estimator.fit(X, y)


def test_folds_without_flips_are_left_out_of_the_mean():
    fitted = _fit_with([None, None, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8])
    assert fitted.skipped_folds_ == 2 and fitted.recovery_results_ == [0.8] * 6
    assert fitted.mean_recovery_ == pytest.approx(0.8)            # was 0.6
    assert fitted.correction_factor_ == pytest.approx(1.25)       # was 1.67
    assert fitted.correction_status_ == "estimated"


def test_half_of_the_folds_must_be_measured():
    assert MIN_MEASURED_FOLD_SHARE == 0.5
    half = _fit_with([None] * 4 + [0.5] * 4)
    assert half.correction_status_ == "estimated" and half.correction_factor_ == pytest.approx(2)
    fewer = _fit_with([None] * 5 + [0.5] * 3)
    assert fewer.correction_status_ == "too_few_flipped_folds"
    assert fewer.is_valid_for_regression_ is False and fewer.mean_recovery_ is None


def test_the_minimum_sample_check_already_gives_every_fold_flips():
    """Why F3 does not occur in the main path: the minimum number of target rows
    (max(ceil(3 / f), 2 * folds)) leaves at least two flips per fold."""
    for fraction in (0.05, 0.1, 0.2, 0.3):
        for folds in (4, 6, 8):
            required = max(int(np.ceil(3 / fraction)), 2 * folds)
            train_rows = required - int(np.ceil(required / folds))
            assert int(train_rows * fraction) >= 2, (fraction, folds)


def test_too_few_flipped_folds_makes_c_unestimable_in_the_handler():
    from pathlib import Path
    source = (Path(__file__).resolve().parent.parent / "src" / "JBGHandler.py").read_text(
        encoding="utf-8")
    block = source.split("statistically_unestimable_statuses = ")[1].split("}")[0]
    assert '"too_few_flipped_folds"' in block
