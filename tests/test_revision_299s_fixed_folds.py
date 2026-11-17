"""299s, JBG v1.1 (DN-01 F6, settled 2026-11-16, option A1): the flip test
behind c uses 4 folds x 2 repeats on every computer. They were chosen from the
CPU count, so c (and D) differed between machines: on synthetic data with
logistic regression from 2.71 to 3.15. 2-, 4- and 8-core machines used 4 x 2
already and are unchanged."""
import warnings
from pathlib import Path

import pytest

from JBGDarkNumbers import DarkNumberCalculator


def test_the_fixed_folds_and_repeats():
    assert (DarkNumberCalculator.FLIP_TEST_FOLDS, DarkNumberCalculator.FLIP_TEST_REPEATS) == (4, 2)


def test_the_handler_no_longer_asks_the_cpu_count():
    source = (Path(__file__).resolve().parent.parent / "src" / "JBGHandler.py").read_text(
        encoding="utf-8")
    block = source.split("def _calculate_dark_number_corrections")[1].split("\n    def ")[0]
    assert "_auto_n_splits_and_repeats(" not in block
    assert "n_splits = DarkNumberCalculator.FLIP_TEST_FOLDS" in block


@pytest.mark.parametrize("cores", [2, 6, 10, 16])
def test_c_is_the_same_whatever_the_cpu_count(monkeypatch, cores):
    import JBGHandler
    import test_dark_number_dense_input as dense
    monkeypatch.setattr(JBGHandler, "cpu_count", lambda: cores, raising=False)
    monkeypatch.setattr(JBGHandler.psutil, "cpu_count", lambda logical=True: cores)
    X, y = dense.dataset()
    models = dense.fitted_models(X, y)
    handler = dense.handler()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        dense.run(handler, X, y, models)
    fits = handler.__dict__.get("dark_number_train_fits")
    corr = tuple(handler.dark_numbers["corr"])
    if not hasattr(test_c_is_the_same_whatever_the_cpu_count, "seen"):
        test_c_is_the_same_whatever_the_cpu_count.seen = (corr, fits)
    assert (corr, fits) == test_c_is_the_same_whatever_the_cpu_count.seen
