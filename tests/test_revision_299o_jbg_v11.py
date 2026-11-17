"""299o, JBG v1.1 (settled 2026-11-16, DN-01 F1, F2 and the bounds on c): a
correction of the standard method that leaves D unchanged in normal cases.
D = -1 ("undefined") when a rate is undefined (TN + FP = 0 or TP + FN = 0,
also a one-label scope) or when c could not be estimated or lies outside
[1, 10]; c is then -1 too. With no false positives and rows outside the
target, D = 0 whatever c is."""
import math

import pandas as pd
import pytest

from JBGDarkNumbers import DarkNumberCalculator as Calc

REAL = pd.Series([1, 1, 0, 0, 0, 1])
PRED_FP = pd.Series([1, 0, 1, 0, 0, 1])          # one FP, one FN
PRED_NO_FP = pd.Series([1, 0, 0, 0, 0, 1])       # no FP
CERTAINTY = pd.Series([0.9, 0.6, 0.7, 0.8, 0.8, 0.95])


def _all_branches(predicted, corr):
    c = Calc()
    return [c.compute_dark_number(REAL, predicted, corr),
            c.compute_dark_number_single_alpha(REAL, predicted, CERTAINTY, corr)[1],
            c.compute_dark_number_separated_alpha(REAL, predicted, CERTAINTY, corr)[1],
            c.compute_dark_number_non_linear(REAL, predicted, CERTAINTY, False, 3, corr)[1],
            c.compute_dark_number_non_linear(REAL, predicted, CERTAINTY, True, 3, corr)[1]]


def test_the_method_version_and_bounds():
    assert Calc.METHOD_VERSION == "1.2"                     # 299u: the agreed reading
    assert (Calc.UNDEFINED, Calc.CORRECTION_MIN, Calc.CORRECTION_MAX) == (-1.0, 1.0, 10.0)


@pytest.mark.parametrize("corr, source, expected", [
    (1.0, "direct", (1.0, "direct")),
    (10.0, "direct", (10.0, "direct")),
    (2.5, "regressed_same_model", (2.5, "regressed_same_model")),
    (10.5, "direct", (-1.0, "undefined/out_of_bounds (direct)")),
    (0.5, "direct", (-1.0, "undefined/out_of_bounds (direct)")),
    (math.inf, "direct", (-1.0, "undefined/out_of_bounds (direct)")),
    (math.nan, "direct", (-1.0, "undefined/out_of_bounds (direct)")),
    (1.0, "fallback/unestimable", (-1.0, "undefined/unestimable")),
])
def test_c_outside_the_bounds_or_unestimable_is_undefined(corr, source, expected):
    assert Calc.bounded_correction(corr, source) == expected


def test_an_undefined_c_makes_d_undefined_when_there_are_false_positives():
    assert _all_branches(PRED_FP, -1.0) == [-1.0] * 5
    assert all(value > 0 for value in _all_branches(PRED_FP, 2.0))     # normal case


def test_without_false_positives_d_is_zero_whatever_c_is():
    for corr in (-1.0, 2.0):
        values = _all_branches(PRED_NO_FP, corr)
        assert values == [0.0] * 5 and all(math.copysign(1, v) == 1 for v in values)


def test_undefined_rates_in_every_branch():
    only_target = pd.Series([1, 1, 1])
    for predicted in (pd.Series([1, 0, 1]), pd.Series([1, 1, 1])):
        c = Calc()
        assert c.compute_dark_number(only_target, predicted, 2.0) == -1.0
        assert c.compute_dark_number_separated_alpha(only_target, predicted,
                                                     pd.Series([0.9, 0.6, 0.8]), 2.0)[1] == -1.0
        assert c.compute_dark_number_non_linear(only_target, predicted,
                                                pd.Series([0.9, 0.6, 0.8]), True, 3, 2.0)[1] == -1.0


def test_the_report_names_the_cause():
    from JBGDarkNumberReporting import build_dark_number_intervals
    rows = pd.DataFrame([
        {"Model type": "D_cv_test - LR", "type": "separated_alpha", "target": "a",
         "alphas": "[1, 1]", "corr": -1.0, "corr_model": "LR",
         "corr_source": "undefined/out_of_bounds (direct)", "dark_number": -1.0},
        {"Model type": "D_cv_full - LR", "type": "separated_alpha", "target": "a",
         "alphas": "[1, 1]", "corr": 2.0, "corr_model": "LR", "corr_source": "direct",
         "dark_number": -1.0},
    ])
    points = build_dark_number_intervals(rows)[0]["points"]
    reasons = {p["label"]: p["reason"] for p in points if p["reason"]}
    assert "undefined correction" in reasons.values() and "undefined rate" in reasons.values()


def test_the_results_tab_says_undefined():
    from JBGWebUI import _load_catalog, translator
    from JBGWebUIResults import DARK_REASONS, readable_dark_table
    detail = {"columns": ["Model type", "corr", "dark_number"],
              "rows": [["D_cv_test - LR", "-1.0", "-1.0"], ["D_cv_full - LR", "2.0", "0.1"]]}
    readable_dark_table(detail, translator("sv"), "sv")
    assert detail["rows"][0][1:] == ["Odefinierad", "Odefinierad"]
    assert detail["rows"][1][1:] == ["2.0", "0.1"]
    catalog = _load_catalog("sv")
    assert DARK_REASONS["undefined rate"] in catalog
    assert DARK_REASONS["undefined correction"] in catalog
