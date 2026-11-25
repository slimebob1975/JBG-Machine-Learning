"""301b (found with 300y, reported 2026-11-24): stacking the Dark Numbers rows
of each estimate raised a pandas FutureWarning when a column was empty in one
block (for example c's interval when c is undefined). The empty column now
takes the other block's type first, so the result is as before and there is no
warning."""
import warnings

import numpy as np
import pandas as pd

from JBGHandler import _concat_rows


def _stacked(top, bottom):
    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        return _concat_rows(pd.DataFrame(top), pd.DataFrame(bottom))


def test_an_empty_column_takes_the_other_blocks_type():
    floats = _stacked({"c": [2.4, 1.1]}, {"c": [np.nan]})
    assert floats["c"].dtype == "float64" and floats["c"].isna().tolist() == [False, False, True]
    reverse = _stacked({"c": [None]}, {"c": [2.5]})
    assert reverse["c"].dtype == "float64" and reverse["c"].tolist()[1] == 2.5
    whole = _stacked({"n": [3, 4]}, {"n": [None]})
    assert whole["n"].dtype == "float64"
    flags = _stacked({"o": [True, False]}, {"o": [None]})
    assert flags["o"].dtype == object and flags["o"].tolist()[:2] == [True, False]
    texts = _stacked({"q": ["reliable"]}, {"q": [None]})
    assert texts["q"].tolist()[0] == "reliable"


def test_columns_in_one_block_only_and_full_blocks_are_unchanged():
    both = _stacked({"a": [1.0], "b": ["x"]}, {"a": [2.0], "c": [3.0]})
    assert list(both.columns) == ["a", "b", "c"] and both["a"].tolist() == [1.0, 2.0]
    plain = pd.concat([pd.DataFrame({"a": [1.0]}), pd.DataFrame({"a": [2.0]})], axis=0)
    pd.testing.assert_frame_equal(_stacked({"a": [1.0]}, {"a": [2.0]}), plain)


def test_the_dark_numbers_computation_gives_no_warning():
    from test_dark_number_dense_input import dataset, fitted_models
    from test_revision_300y_standard_estimator import _handler, _run
    X, y = dataset()
    ph, _ = _handler(c_max=1.05)                 # undefined c: empty interval columns
    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        _run(ph, fitted_models(X, y))
    assert not ph.dark_numbers.empty
