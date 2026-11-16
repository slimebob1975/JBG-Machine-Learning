"""299i2 (gate 2026-11-13): an SQL feature investigation stopped at once with
"The truth value of an array ... is ambiguous": the SQL data layer returns the
fetched rows as a NumPy array (the CSV layer as a list), and the data check
before the search tested them with "not rows". The check accepts both, and a
DataFrame, and still finds lost values."""
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from JBGFeaturePreservation import validate_investigation_feature_preservation

COLUMNS = ["id", "f1", "f2", "target"]
CONFIG = SimpleNamespace(get_numerical_column_names=lambda: ["f1", "f2"])


def _rows():
    return [[1, "5.1", "3.5", "a"], [2, "4.9", "3.0", "b"], [3, "6.2", "x", "c"]]


@pytest.mark.parametrize("shape", [list, np.array, lambda rows: pd.DataFrame(rows)])
def test_rows_as_a_list_an_array_or_a_frame_are_checked(shape):
    converted = pd.DataFrame({"f1": [5.1, 4.9, 6.2], "f2": [3.5, 3.0, 2.0]})
    validate_investigation_feature_preservation(shape(_rows()), COLUMNS, CONFIG, converted)
    lost = pd.DataFrame({"f1": [5.1, 4.9, 6.2], "f2": [3.5, 3.0, None]})
    with pytest.raises(ValueError, match="f2: 3 nonempty source values, 2 retained"):
        validate_investigation_feature_preservation(shape(_rows()), COLUMNS, CONFIG, lost)


@pytest.mark.parametrize("rows", [None, [], np.empty((0, 4))])
def test_no_rows_are_left_to_the_caller(rows):
    validate_investigation_feature_preservation(rows, COLUMNS, CONFIG, pd.DataFrame())
