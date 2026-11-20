"""300m (reported 2026-11-20): a real run with a rare target class (about 1 %)
and a closely fitting voting ensemble got c = inf, so three of the four Dark
Number estimates were undefined. JBG 1.3 averaged the flip test's per-part
ratios r_unseen / r_in, and one part where the model recognised none of its
(about 12) relabelled rows made the mean infinite. c is now the ratio of the
means (= the quotient of the table's two columns), with a bootstrap interval
over the parts; it is infinite only when r_in is 0 in every part."""
import math

import pytest

from JBGDarkNumberOutOfFold import overtraining_factor


def test_one_part_without_recognition_no_longer_makes_c_infinite():
    pairs = [(0.0, 0.62)] + [(0.33, 0.62)] * 7
    factor = overtraining_factor(pairs)
    assert factor["c"] == pytest.approx(0.62 / (0.33 * 7 / 8))
    assert factor["quality"] in ("reliable", "uncertain") and factor["c_low"] <= factor["c"]


def test_c_is_the_quotient_of_the_two_columns():
    pairs = [(0.4, 0.6), (0.5, 0.7), (0.45, 0.65), (0.55, 0.6)]
    mean_in = sum(p[0] for p in pairs) / 4
    mean_unseen = sum(p[1] for p in pairs) / 4
    c_in, c_unseen = 1 / mean_in, 1 / mean_unseen
    assert overtraining_factor(pairs)["c"] == pytest.approx(c_in / c_unseen)


def test_undefined_only_when_nothing_is_recognised_anywhere():
    assert math.isinf(overtraining_factor([(0.0, 0.6)] * 8)["c"])


def test_the_interval_is_reproducible():
    pairs = [(0.3, 0.6), (0.2, 0.5), (0.35, 0.7), (0.25, 0.55)] * 2
    assert overtraining_factor(pairs) == overtraining_factor(pairs)
