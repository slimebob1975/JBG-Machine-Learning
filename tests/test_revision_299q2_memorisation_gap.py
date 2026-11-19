"""299q2 (settled 2026-11-16): the memorisation warning compares the
correction model's training fit with its accuracy on unseen rows. Warn when
the fit is at least 0.95 and at least 5 percentage points above the unseen
accuracy (an easy problem gives high values for both and is not flagged).
Without an unseen accuracy, 299q's fit-only rule (0.99) applies."""
import warnings

import pandas as pd
import pytest

from JBGDarkNumberReporting import build_dark_number_intervals
from JBGDarkNumbers import DarkNumberCalculator as Calc


def test_the_values():
    assert (Calc.MEMORISATION_FIT, Calc.MEMORISATION_GAP, Calc.MEMORISATION_THRESHOLD) == \
        (0.95, 0.05, 0.99)


@pytest.mark.parametrize("fit, unseen, expected", [
    (0.96, 0.85, True),          # memorises
    (1.0, 0.95, True),           # exactly the gap
    (0.96, 0.93, False),         # an easy problem: high on both
    (1.0, 0.97, False),
    (0.94, 0.50, False),         # below the fit
    (0.995, None, True),         # no unseen accuracy: fit only, 0.99
    (0.98, None, False),
    (None, 0.5, False), ("x", 0.5, False), (float("nan"), 0.5, False),
])
def test_the_rule(fit, unseen, expected):
    assert Calc.memorises(fit, unseen) is expected


def test_the_summary_uses_the_unseen_accuracy():
    rows = pd.DataFrame([
        {"Model type": "D_cv_test - T", "type": "separated_alpha", "target": "a", "corr": 2.0,
         "corr_model": "T", "corr_source": "direct", "corr_train_fit": 0.97,
         "corr_unseen_accuracy": 0.96, "dark_number": 0.2},
        {"Model type": "D_cv_full - T", "type": "separated_alpha", "target": "a", "corr": 2.0,
         "corr_model": "T", "corr_source": "direct", "corr_train_fit": 0.97,
         "corr_unseen_accuracy": 0.80, "dark_number": 0.3},
    ])
    points = {p["label"]: p for p in build_dark_number_intervals(rows)[0]["points"]}
    assert points["D_cv_test"]["memorises"] is False and points["D_cv_full"]["memorises"] is True


def test_the_handler_records_the_unseen_accuracy():
    import test_dark_number_dense_input as dense
    X, y = dense.dataset()
    models = dense.fitted_models(X, y)
    handler = dense.handler()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        dense.run(handler, X, y, models)
    frame = handler.dark_numbers
    columns = list(frame.columns)
    assert columns.index("corr_unseen_accuracy") == columns.index("corr_train_fit") + 1
    known = handler.__dict__["dark_number_unseen_accuracy"]
    assert known and all(0.0 <= v <= 1.0 for v in known.values())
    values = [v for v in frame["corr_unseen_accuracy"] if v is not None and v == v]
    assert values and set(values) <= set(known.values())


def test_the_texts():
    from JBGWebUI import _load_catalog
    from JBGWebUIResults import DARK_COLUMNS
    catalog = _load_catalog("sv")
    assert catalog[DARK_COLUMNS["corr_unseen_accuracy"]] == "Träffsäkerhet på osedd del"   # 300i
    assert ";" not in "".join(catalog.values()).replace("charset=UTF-8", "")
