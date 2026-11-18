"""The out-of-fold correction factor (revision 300e, DN-03, settled 2026-11-18).

The flip test behind c measured recovery on the very rows the model was fitted
on (DN-01 F4), so a model that memorises its training rows reproduced their
wrong labels and c was overstated. Here recovery is measured out-of-fold:

1. A fraction of the target rows (the configured flip fraction, 20 % by
   default) is relabelled once, to another class drawn by the classes' sizes.
2. Five stratified folds; each relabelled row is predicted by a model trained
   on the other four folds (which hold relabelled rows too, but not that one).
3. r = the share of relabelled rows predicted as the target; c = 1 / r.
4. Repeated with new relabelled rows and new folds: at least 3 and at most 10
   times, stopping when the 90 % interval of c is within +/-10 % of c.

c's uncertainty is the 90 % interval over the repeats (a t-interval on the
recoveries, turned into c). Its quality state: reliable (1 <= c <= 10 and the
interval within +/-25 %), uncertain (a wider interval: used, but flagged), or
not estimable (outside 1-10 or not computable: D is undefined).

During the transition (agreed 2026-11-18) the Dark Number keeps using the
in-sample c; this c and the Dark Number it would give are shown beside it.
"""
from __future__ import annotations

import math

import numpy as np
from sklearn.base import clone
from sklearn.model_selection import StratifiedKFold

FOLDS = 5
MIN_REPEATS, MAX_REPEATS = 3, 10
STOP_HALFWIDTH = 0.10          # stop when the 90 % interval is within +/-10 % of c
RELIABLE_HALFWIDTH = 0.25      # reliable when within +/-25 %
CORRECTION_MIN, CORRECTION_MAX = 1.0, 10.0
_T90 = {2: 2.920, 3: 2.353, 4: 2.132, 5: 2.015, 6: 1.943, 7: 1.895, 8: 1.860, 9: 1.833}


def _t90(n: int) -> float:
    """The two-sided 90 % t quantile for n repeats (n - 1 degrees of freedom)."""
    return _T90.get(n - 1, 1.645 if n > 10 else 6.314)


def _flip(y, positive_class, fraction, rng):
    """y with ``fraction`` of the target rows relabelled; returns (y, flipped indices)."""
    y = np.asarray(y, dtype=object).copy()
    targets = np.flatnonzero(y == positive_class)
    others = [c for c in np.unique(y) if c != positive_class]
    n_flip = int(len(targets) * fraction)
    if n_flip == 0 or not others:
        return y, np.array([], dtype=int)
    chosen = rng.choice(targets, size=n_flip, replace=False)
    sizes = np.array([np.sum(y == c) for c in others], dtype=float)
    labels = rng.choice(len(others), size=n_flip, p=sizes / sizes.sum())
    y[chosen] = np.asarray(others, dtype=object)[labels]
    return y, chosen


def _recovery(estimator, X, y, positive_class, fraction, seed, sampling_policy):
    """One repeat: the share of relabelled rows predicted back as the target."""
    rng = np.random.default_rng(seed)
    flipped_y, chosen = _flip(y, positive_class, fraction, rng)
    if len(chosen) == 0:
        return None
    is_flipped = np.zeros(len(flipped_y), dtype=bool)
    is_flipped[chosen] = True
    recovered = 0
    folds = StratifiedKFold(n_splits=FOLDS, shuffle=True, random_state=seed)
    for train, test in folds.split(np.zeros(len(flipped_y)), flipped_y.astype(str)):
        rows = test[is_flipped[test]]
        if len(rows) == 0:
            continue
        model = clone(estimator)
        X_train, y_train = X[train], flipped_y[train]
        if sampling_policy and sampling_policy != "PIPELINE":
            from JBGDarkNumberSampling import resample, without_samplers
            model = without_samplers(model)
            X_train, y_train, _ = resample(sampling_policy, X_train, y_train,
                                           is_flipped[train], seed)
        model.fit(X_train, y_train)
        recovered += int(np.sum(np.asarray(model.predict(X[rows])) == positive_class))
    return recovered / len(chosen)


def estimate(estimator, X, y, positive_class, flip_fraction=0.2, random_state=42,
             sampling_policy="PIPELINE") -> dict:
    """The out-of-fold c with its 90 % interval, repeats used and quality state."""
    X = X.tocsr() if hasattr(X, "tocsr") else np.asarray(X)
    y = np.asarray(y, dtype=object)
    recoveries = []
    for repeat in range(MAX_REPEATS):
        r = _recovery(estimator, X, y, positive_class, flip_fraction,
                      int(random_state or 0) + 1000 + repeat, sampling_policy)
        if r is None:
            return _result(None, None, None, recoveries, "not_estimable")
        recoveries.append(r)
        if len(recoveries) >= MIN_REPEATS:
            c, low, high = _interval(recoveries)
            if c is not None and (high - low) / 2 <= STOP_HALFWIDTH * c:
                break
    c, low, high = _interval(recoveries)
    if c is None or not (CORRECTION_MIN <= c <= CORRECTION_MAX):
        return _result(c, low, high, recoveries, "not_estimable")
    quality = "reliable" if (high - low) / 2 <= RELIABLE_HALFWIDTH * c else "uncertain"
    return _result(c, low, high, recoveries, quality)


def _interval(recoveries):
    values = np.asarray(recoveries, dtype=float)
    mean = float(values.mean())
    if mean <= 0:
        return None, None, None
    half = _t90(len(values)) * float(values.std(ddof=1)) / math.sqrt(len(values)) \
        if len(values) > 1 else math.inf
    low_r, high_r = max(mean - half, 1e-9), mean + half
    return 1.0 / mean, 1.0 / high_r, (1.0 / low_r if low_r > 1e-9 else math.inf)


def _result(c, low, high, recoveries, quality):
    return {"c": c, "c_low": low, "c_high": high, "repeats": len(recoveries),
            "recoveries": [float(r) for r in recoveries], "quality": quality}
