"""299r, JBG v1.1 (DN-01 F5, settled 2026-11-16, option A): with more than two
classes, each row flipped in the flip test gets a random other class, drawn in
proportion to the other classes' sizes in the training part. It always got the
first other class in sorted order, so c depended on the class names. Two
classes are unchanged (the 299n pins still hold)."""
from collections import Counter

import numpy as np

from JBGDarkNumberCorrectionFactor import evaluate_split
from test_revision_299n_dn01_baseline import Rule


def _flipped(y, target, seed):
    seen = {}

    class Recorder(Rule):
        def fit(self, X, labels):
            seen["y"] = np.asarray(labels)
            return super().fit(X, labels)
    X = np.c_[np.arange(float(len(y))), np.zeros(len(y))]
    evaluate_split(Recorder(), X, y, np.arange(len(y)), seed, 0.5, target, "predict", 7)
    return Counter(seen["y"][(y == target) & (seen["y"] != target)])


def test_flips_are_spread_over_the_other_classes_by_size():
    y = np.array(["t"] * 200 + ["big"] * 600 + ["small"] * 200)
    total = Counter()
    for seed in range(20):
        total += _flipped(y, "t", seed)
    share = total["big"] / (total["big"] + total["small"])
    assert 0.70 <= share <= 0.80                                  # 600 / 800 = 0.75


def test_the_result_no_longer_depends_on_the_class_names():
    a = _flipped(np.array(["t"] * 100 + ["a"] * 100 + ["z"] * 100), "t", 0)
    renamed = _flipped(np.array(["t"] * 100 + ["z"] * 100 + ["a"] * 100), "t", 0)
    assert a["a"] > 0 and a["z"] > 0 and renamed["a"] > 0 and renamed["z"] > 0


def test_two_classes_are_unchanged_and_draw_nothing():
    y = np.array(["t"] * 100 + ["o"] * 100)
    flipped = _flipped(y, "t", 3)
    assert set(flipped) == {"o"} and flipped["o"] == 50


def test_the_draw_is_reproducible():
    y = np.array(["t"] * 100 + ["a"] * 150 + ["b"] * 50)
    assert _flipped(y, "t", 5) == _flipped(y, "t", 5)
