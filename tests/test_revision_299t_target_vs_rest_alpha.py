"""299t, JBG v1.1 (DN-01 F7, settled 2026-11-16, reading 1): the alpha weights
use the certainty behind each verdict, target against the rest: P(target) on
false positives (as before) and 1 - P(target) on false negatives. They used the
probability of the predicted label, which with more than two classes is less
than the certainty that a row is not the target. Two classes: unchanged."""
import warnings

import numpy as np
import pandas as pd
import pytest

from JBGDarkNumbers import DarkNumberCalculator

CLASSES = ["a", "b", "c"]
REAL = pd.Series(["a", "a", "b", "c", "b", "a"])
PRED = pd.Series(["b", "a", "a", "c", "b", "c"])          # FN for a: rows 0 and 5, FP for a: row 2
PROBS = pd.DataFrame([[0.30, 0.40, 0.30], [0.80, 0.10, 0.10], [0.50, 0.30, 0.20],
                      [0.10, 0.20, 0.70], [0.20, 0.60, 0.20], [0.35, 0.25, 0.40]],
                     columns=CLASSES)
MAXPROB = PROBS.max(axis=1)


def test_the_certainty_is_target_against_the_rest():
    predicted_a = (PRED == "a").astype(int)
    certainty = DarkNumberCalculator.target_vs_rest_certainty(PROBS, "a", predicted_a, MAXPROB)
    assert certainty[0] == pytest.approx(0.70)          # FN: not-a, was 0.40 (P(b))
    assert certainty[5] == pytest.approx(0.65)          # FN: was 0.40 (P(c))
    assert certainty[2] == pytest.approx(0.50)          # FP: P(a), as before
    same = DarkNumberCalculator.target_vs_rest_certainty(None, "a", predicted_a, MAXPROB)
    assert same is MAXPROB                              # without class probabilities: as before


def test_multiclass_alphas_rise_to_the_not_target_certainty():
    calc = DarkNumberCalculator()
    corrs = {c: 2.0 for c in CLASSES}
    before = calc.compute_dark_numbers(REAL, PRED, MAXPROB, type="separated_alpha", corrs=corrs)
    after = calc.compute_dark_numbers(REAL, PRED, MAXPROB, type="separated_alpha", corrs=corrs,
                                      class_probabilities=PROBS)
    old = before.set_index("target").loc["a", "alphas"]
    new = after.set_index("target").loc["a", "alphas"]
    assert old == pytest.approx([0.50, 0.40]) and new == pytest.approx([0.50, 0.675])
    assert after.set_index("target").loc["a", "dark_number"] > \
        before.set_index("target").loc["a", "dark_number"]


def test_two_classes_are_unchanged():
    real = pd.Series(["x", "y", "x", "y", "x", "y"])
    pred = pd.Series(["x", "x", "y", "y", "x", "x"])
    probs = pd.DataFrame([[0.9, 0.1], [0.6, 0.4], [0.3, 0.7], [0.2, 0.8], [0.8, 0.2], [0.55, 0.45]],
                         columns=["x", "y"])
    calc = DarkNumberCalculator()
    corrs = {"x": 1.5, "y": 1.5}
    for kind in ("single_alpha", "separated_alpha", "non_linear_alpha"):
        old = calc.compute_dark_numbers(real, pred, probs.max(axis=1), type=kind, corrs=corrs)
        new = calc.compute_dark_numbers(real, pred, probs.max(axis=1), type=kind, corrs=corrs,
                                        class_probabilities=probs)
        assert list(new["dark_number"]) == pytest.approx(list(old["dark_number"]), abs=1e-12)


def test_the_handler_passes_the_class_probabilities_and_starts_afresh():
    import test_dark_number_dense_input as dense
    X, y = dense.dataset()
    models = dense.fitted_models(X, y)
    handler = dense.handler()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        dense.run(handler, X, y, models)
        first = dict(handler.__dict__["dark_number_class_probabilities"])
        dense.run(handler, X, y, models)
    second = handler.__dict__["dark_number_class_probabilities"]
    assert set(first) == set(second) and "Combined (legacy full-data)" in second
    for name, frame in second.items():
        assert np.allclose(frame.sum(axis=1), 1.0) or name.startswith("Combined")
    assert len(handler.__dict__["dark_number_combined_parts"]) == \
        sum(1 for name in second if "_full" in name)
