"""The out-of-fold correction factor (DN-03; revision 300e, revised 300g).

The flip test behind c measured recovery on the very rows the model was fitted
on (DN-01 F4), so a model that memorises its training rows reproduced their
wrong labels and c was overstated. The out-of-fold c measures recovery on rows
the model has not seen.

300g (2026-11-19): measured inside the existing flip test, at no extra fit.
300e ran its own 15-50 fits one after another, which took many hours on large
data. Each of the flip test's folds trains a copy on 75 % of the rows with some
target rows relabelled; that copy now also predicts the fold's unseen target
rows (the other 25 %). A model cannot see the label of a row it was not trained
on, so the share it still predicts as the target is the recovery a relabelled
row would have had. With 4 folds x 2 repeats this gives 8 values:

    r = the mean of the fold values, c = 1 / r,
    a 90 % interval from a t-interval on the fold values, turned into c,
    quality: reliable (1 <= c <= 10, interval within +/-25 %), uncertain
    (wider: used, flagged) or not estimable (outside 1-10 or not computable).

During the transition (agreed 2026-11-18) the Dark Number keeps the in-sample
c; this c and the Dark Number it would give are shown beside it.
"""
from __future__ import annotations

import math

import numpy as np

RELIABLE_HALFWIDTH = 0.25      # reliable when the 90 % interval is within +/-25 %
CORRECTION_MIN, CORRECTION_MAX = 1.0, 20.0                # 300v: was 10
_T90 = {1: 6.314, 2: 2.920, 3: 2.353, 4: 2.132, 5: 2.015, 6: 1.943, 7: 1.895, 8: 1.860,
        9: 1.833, 10: 1.812, 11: 1.796, 12: 1.782, 13: 1.771, 14: 1.761, 15: 1.753}


def _t90(n: int) -> float:
    """The two-sided 90 % t quantile for n values (n - 1 degrees of freedom)."""
    return _T90.get(n - 1, 1.645)


def interval(recoveries):
    """(c, lower, upper) from the fold recoveries, or (None, None, None)."""
    values = np.asarray([r for r in recoveries if r is not None], dtype=float)
    if len(values) == 0 or float(values.mean()) <= 0:
        return None, None, None
    mean = float(values.mean())
    half = _t90(len(values)) * float(values.std(ddof=1)) / math.sqrt(len(values)) \
        if len(values) > 1 else math.inf
    low_r, high_r = max(mean - half, 1e-9), mean + half
    return 1.0 / mean, 1.0 / high_r, (1.0 / low_r if low_r > 1e-9 else math.inf)


def summarise(recoveries) -> dict:
    """The out-of-fold c with its 90 % interval, the folds used and the quality."""
    values = [float(r) for r in recoveries if r is not None]
    c, low, high = interval(values)
    if c is None or not (CORRECTION_MIN <= c <= CORRECTION_MAX):
        quality = "not_estimable"
    else:
        quality = "reliable" if (high - low) / 2 <= RELIABLE_HALFWIDTH * c else "uncertain"
    return {"c": c, "c_low": low, "c_high": high, "repeats": len(values),
            "recoveries": values, "quality": quality}


def _quantile(values, q: float) -> float:
    """300u (found 2026-11-24): a quantile of resampled ratios, some of which
    may be infinite (a resample of parts that all have r_in = 0). Between two
    infinite values NumPy's interpolation gives nan (inf - inf), with a
    RuntimeWarning, and max(1.0, nan) is 1.0: the upper bound of c then read 1
    and an unbounded c was called reliable. nan only arises in the infinite
    region, so it is infinite; finite quantiles are unchanged."""
    with np.errstate(invalid="ignore"):
        value = float(np.quantile(values, q))
    return math.inf if math.isnan(value) else value


def overtraining_factor(pairs, resamples: int = 2000, seed: int = 20261120,
                        c_max: float = CORRECTION_MAX) -> dict:
    """The part of c that comes from overtraining only (JBG 1.3):
    c = max(1, mean(r_unseen) / mean(r_in)) = c_in / c_unseen, the quotient of
    the two columns shown in the calculation table. Both recoveries come from
    the same models trained with the same relabelled rows, so the model's
    ordinary misses (class overlap) and the effect of the relabelled labels
    cancel in the ratio; what is left is the loss on rows the model was trained
    on, i.e. memorisation.

    300m (2026-11-20): the ratio of the means over the flip test's parts. 300k
    averaged the parts' ratios, so a single part where the model recognised
    none of its relabelled rows (r_in = 0, likely with few target rows and a
    closely fitting model) made c infinite and the Dark Number undefined.
    Now such a part only lowers the mean; c is infinite only when r_in is 0
    in every part. The 90 % interval comes from resampling the parts
    (bootstrap, fixed seed)."""
    pairs = [(float(r_in), float(r_unseen)) for r_in, r_unseen in pairs
             if r_in is not None and r_unseen is not None]
    if not pairs:
        return {"c": None, "c_low": None, "c_high": None, "folds": 0, "quality": "not_estimable"}
    values = np.asarray(pairs, dtype=float)
    mean_in, mean_unseen = float(values[:, 0].mean()), float(values[:, 1].mean())
    if mean_in <= 0:
        return {"c": math.inf, "c_low": None, "c_high": None, "folds": len(pairs),
                "quality": "not_estimable"}
    c = max(1.0, mean_unseen / mean_in)
    rng = np.random.default_rng(seed)
    picks = rng.integers(0, len(values), size=(resamples, len(values)))
    sample_in = values[:, 0][picks].mean(axis=1)
    sample_unseen = values[:, 1][picks].mean(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratios = np.where(sample_in > 0, sample_unseen / np.where(sample_in > 0, sample_in, 1),
                          np.inf)
    low = max(1.0, _quantile(ratios, 0.05))
    high = max(1.0, _quantile(ratios, 0.95))
    if not (CORRECTION_MIN <= c <= c_max):
        quality = "not_estimable"
    elif math.isinf(high) or (high - low) / 2 > RELIABLE_HALFWIDTH * c:
        quality = "uncertain"
    else:
        quality = "reliable"
    return {"c": c, "c_low": low, "c_high": high, "folds": len(pairs), "quality": quality}
