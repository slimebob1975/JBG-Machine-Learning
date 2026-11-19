"""300e, DN-03 (settled 2026-11-18; measurement revised in 300g): the
correction factor c measured out-of-fold, shown beside the in-sample c during
the transition (the Dark Number keeps the in-sample c). Since 300g it comes
from the flip test's own folds (no extra fits): a 90 % interval and a quality
state, reliable (within +/-25 %), uncertain (used, flagged) or not estimable
(outside 1-10: undefined)."""
import warnings

import pandas as pd
import pytest

from JBGDarkNumberOutOfFold import interval, summarise


def test_the_interval():
    c, low, high = interval([0.5, 0.5, 0.5])
    assert c == pytest.approx(2.0) and low == pytest.approx(2.0) and high == pytest.approx(2.0)
    c, low, high = interval([0.4, 0.6, 0.5, 0.5])
    assert low < c < high
    assert interval([]) == (None, None, None) and interval([0.0, 0.0]) == (None, None, None)


def test_the_quality_states():
    assert summarise([0.5] * 8)["quality"] == "reliable"
    assert summarise([0.2, 0.9, 0.3, 0.8])["quality"] == "uncertain"
    assert summarise([0.05] * 8)["quality"] == "not_estimable"          # c = 20
    assert summarise([])["quality"] == "not_estimable"
    assert summarise([0.5, None, 0.5])["repeats"] == 2


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
