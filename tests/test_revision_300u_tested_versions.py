"""300u (2026-11-24): the tested versions (constraints-tested.txt and
docs/dependencies.md, agreed 2026-11-24), and c's upper bound when resamples of
the flip test's parts are infinite (found behind the 300k test's NumPy
RuntimeWarning)."""
import math
import re
import warnings
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CONSTRAINTS = (ROOT / "constraints-tested.txt").read_text(encoding="utf-8")
DOC = (ROOT / "docs" / "dependencies.md").read_text(encoding="utf-8")


def _name(text):
    return re.sub(r"[-_.]+", "-", text).lower()


def _pins():
    pins = {}
    for line in CONSTRAINTS.splitlines():
        if line.strip() and not line.startswith("#"):
            match = re.fullmatch(r"([A-Za-z0-9_.\-]+)==([0-9A-Za-z.+\-]+)", line.strip())
            assert match, line
            assert _name(match.group(1)) not in pins, line
            pins[_name(match.group(1))] = match.group(2)
    return pins


# --- The tested versions ----------------------------------------------------------------

def test_every_requirement_has_a_tested_version():
    pins = _pins()
    for name in ("requirements.txt", "requirements-fastapi.txt", "requirements-optional-dill.txt"):
        for line in (ROOT / name).read_text(encoding="utf-8").splitlines():
            line = line.split("#")[0].strip()
            if line:
                assert _name(re.split(r"[<>=!~\[ ]", line)[0]) in pins, (name, line)


def test_the_requirements_stay_unpinned():
    text = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert "==" not in text and "catboost>=1.2.8,<2" in text


def test_the_constraints_work_everywhere():
    pins = _pins()
    assert "pywin32" not in pins and "pywinpty" not in pins
    assert len(pins) == 41                     # 301g: contourpy, used directly
    assert "python -m pip install -r requirements.txt -r requirements-fastapi.txt " \
           "-c constraints-tested.txt" in CONSTRAINTS


def test_the_document_agrees_with_the_constraints():
    pins = _pins()
    rows = re.findall(r"^\| ([A-Za-z][A-Za-z0-9_.\-]*) \| ([0-9][0-9A-Za-z.+\-]*) \|", DOC, re.M)
    assert len(rows) >= 10
    for name, version in rows:
        assert pins[_name(name)] == version, name
    assert "-c constraints-tested.txt" in DOC and "1404" in DOC


def test_the_catboost_range_holds_the_tested_version():
    major, minor, patch = map(int, _pins()["catboost"].split("."))
    assert (1, 2, 8) <= (major, minor, patch) < (2, 0, 0)


# --- c's upper bound --------------------------------------------------------------------

def test_an_infinite_resample_gives_an_infinite_upper_bound():
    from JBGDarkNumberOutOfFold import overtraining_factor
    with warnings.catch_warnings():
        warnings.simplefilter("error")          # the NumPy RuntimeWarning is gone
        factor = overtraining_factor([(0.0, 0.6), (0.3, 0.6)])
    assert factor["c"] == pytest.approx(4.0)
    assert factor["c_low"] == pytest.approx(2.0)
    assert math.isinf(factor["c_high"])          # was 1.0, below the lower bound
    assert factor["quality"] == "uncertain"      # was "reliable"


def test_finite_bounds_are_unchanged():
    from JBGDarkNumberOutOfFold import overtraining_factor
    factor = overtraining_factor([(0.0, 0.6), (0.3, 0.6), (0.3, 0.6), (0.3, 0.6)])
    assert (factor["c_low"], factor["c_high"]) == (pytest.approx(2.0), pytest.approx(8.0))
    steady = overtraining_factor([(0.3, 0.6)] * 8)
    assert steady["c_low"] == steady["c_high"] == pytest.approx(2.0)


def test_the_quantile_keeps_finite_values():
    import numpy as np
    from JBGDarkNumberOutOfFold import _quantile
    assert _quantile(np.array([1.0, 2.0, 3.0]), 0.5) == pytest.approx(2.0)
    assert math.isinf(_quantile(np.array([1.0, math.inf, math.inf, math.inf]), 0.95))


def test_the_table_shows_infinity():
    from JBGWebUI import _number_text
    assert _number_text(math.inf) == "∞" and _number_text(-math.inf) == "−∞"
    assert _number_text(2.4423, "sv") == "2,442" and _number_text(2.0) == "2"
