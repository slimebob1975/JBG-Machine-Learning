"""299z (agreed 2026-11-16): a validation study of JBG 1.2 against a known
truth, before deciding how much of the v2 plan is needed. Synthetic populations
with an exact hidden share, models trained on the registered labels, the
engine's own Dark Number computation, and pre-registered thresholds
(docs/dark_numbers/DN-06_v12_validation_protocol.md)."""
import math

import numpy as np
import pandas as pd
import pytest

from JBGDarkNumberStudy import (REST, TARGET, THRESHOLDS, Cell, broken_cells, excluded_cells,
                                feasible, main_cells, population, run_once, summarise,
                                true_hidden_share)


def test_the_matrix():
    # 299z2: H = 10 % and 20 % with a 15 % target share are impossible or extreme
    # (63 % / all of the target rows hidden): 8 of 60 cells excluded.
    assert len(main_cells()) == 52 and all(c.assumptions_hold for c in main_cells())
    assert {(c.hidden_share, c.target_share) for c in excluded_cells()} == \
        {(0.10, 0.15), (0.20, 0.15)}
    assert feasible(Cell(0.05, 0.15, "weak")) and feasible(Cell(0.20, 0.50, "weak"))
    with pytest.raises(ValueError, match="infeasible"):
        population(Cell(0.20, 0.15, "weak"), 1)
    assert len(broken_cells()) == 8 and not any(c.assumptions_hold for c in broken_cells())


@pytest.mark.parametrize("share", [0.0, 0.02, 0.10, 0.20])
def test_one_sided_hiding_gives_the_exact_hidden_share(share):
    X, registered, true = population(Cell(share, 0.5, "medium"), 7)
    assert true_hidden_share(registered, true) == pytest.approx(share, abs=0.002)
    assert ((registered == TARGET) & (true == REST)).sum() == 0     # one-sided


def test_broken_mechanisms():
    _, registered, true = population(Cell(0.10, 0.5, "medium", "two_sided"), 7)
    assert ((registered == TARGET) & (true == REST)).sum() > 0      # false registrations
    X, registered, true = population(Cell(0.10, 0.5, "medium", "feature_dependent"), 7)
    hidden = (registered == REST) & (true == TARGET)
    kept = (registered == TARGET)
    assert X.loc[hidden, 0].mean() < X.loc[kept, 0].mean()          # weaker cases hidden


def test_a_run_compares_the_four_estimates_with_the_truth():
    rows = run_once(Cell(0.10, 0.5, "strong", rows=800), 3)
    frame = pd.DataFrame(rows)
    assert set(frame["estimate"]) == {"D_cv_test", "D_cv_full", "D_retrained_full",
                                      "Combined (legacy full-data)"}
    assert frame["true_H"].between(0.03, 0.20).all()               # the test part varies
    assert frame.loc[frame["estimate"] == "D_cv_test", "c"].iloc[0] == 1.0   # v1.2: no c
    assert (frame["D"].dropna().between(0, 1)).all()


def _results(D, truth, share=0.10, separation="strong", undefined=False):
    return pd.DataFrame([{"hidden_share": share, "target_share": 0.5, "separation": separation,
                          "mechanism": "one_sided", "model": "logistic", "estimate": "D_cv_test",
                          "true_H": t, "D": None if undefined else d, "undefined": undefined,
                          "capped": False, "memorisation_warning": False, "seconds": 1.0}
                         for d, t in zip(D, truth)])


def test_the_verdicts_follow_the_thresholds():
    good = summarise(_results([0.11, 0.09, 0.105, 0.095], [0.10] * 4))
    assert good["verdict"].iloc[0] == "pass" and good["bias_pp"].iloc[0] == pytest.approx(0.0)
    biased = summarise(_results([0.19, 0.20, 0.21, 0.18], [0.10] * 4))
    assert biased["verdict"].iloc[0] == "fail" and biased["bias_pp"].iloc[0] > 5
    zero = summarise(_results([0.0] * 9 + [0.03], [0.0] * 10, share=0.0))
    assert zero["verdict"].iloc[0] == "pass"                        # 1 of 10 above 2 points
    zero_alarm = summarise(_results([0.03, 0.03, 0.0, 0.0], [0.0] * 4, share=0.0))
    assert zero_alarm["verdict"].iloc[0] == "fail"
    assert THRESHOLDS["mae_pp"] == 3.0 and THRESHOLDS["undefined_share"] == 0.20


def test_too_many_undefined_fails_with_good_separation():
    rows = pd.concat([_results([0.10, 0.10], [0.10] * 2),
                      _results([0.0, 0.0], [0.10] * 2, undefined=True)])
    assert summarise(rows)["verdict"].iloc[0] == "fail"
