"""Sampling policies for the flip test behind the Dark Number correction factor
(revision 299y, DN-02, settled 2026-11-16).

The flip test trains a copy of the winning pipeline on training data in which
some target rows were deliberately relabelled. By default (PIPELINE) the copy
keeps the pipeline's own over- and undersampling, as before. With the target
class in the majority, SMOTE then oversamples the post-flip minority, which is
largely made of the flipped rows, and so manufactures more mislabelled data:
recovery drops and c rises because of the sampling (a warning says so).

The other policies switch the pipeline's sampler steps off in the copy and
resample the flipped training data themselves, never touching validation or
test rows:

- NONE: no over- or undersampling.
- SMOTE: ordinary SMOTE on the flipped training data.
- CLEAN_SMOTE: synthetic rows only from unflipped rows (parents and
  neighbours); flipped rows stay in training but never seed new rows. With
  fewer than k + 1 eligible rows in a class to oversample, that fold falls back
  to NONE (flagged).
- UNDER: random undersampling of the post-flip classes to the smallest
  class's size (1 : 1; ratio controls are in the backlog).
"""
from __future__ import annotations

import numpy as np
from scipy import sparse as scipy_sparse

POLICIES = ("PIPELINE", "NONE", "SMOTE", "CLEAN_SMOTE", "UNDER")
DEFAULT_POLICY = "PIPELINE"
SMOTE_NEIGHBOURS = 5


def _sampler_names() -> set:
    from JBGMeta import Oversampling, Undersampling
    return {member.name for member in Oversampling} | {member.name for member in Undersampling}


def _no_sampling_names() -> set:
    from JBGMeta import Oversampling, Undersampling
    return {Oversampling.NOG.name, Undersampling.NUG.name}


def _is_sampler_step(name: str) -> bool:
    name = str(name)
    return name in _sampler_names() or name.startswith("UNDER_")


def has_oversampler(estimator) -> bool:
    """Whether the pipeline oversamples (a sampler step other than "none")."""
    from JBGMeta import Oversampling
    over = {member.name for member in Oversampling} - _no_sampling_names()
    return any(str(name) in over and step not in (None, "passthrough")
               for name, step in getattr(estimator, "steps", []) or [])


def without_samplers(estimator):
    """A copy of the pipeline with its sampler steps switched off."""
    if not hasattr(estimator, "steps"):
        return estimator
    names = [name for name, _ in estimator.steps if _is_sampler_step(name)]
    if names:
        estimator.set_params(**{name: "passthrough" for name in names})
    return estimator


def contamination_risk(estimator, y, target, policy: str) -> bool:
    """299y: the default keeps the pipeline's SMOTE, and the target is the
    majority class, so its flipped rows become the minority SMOTE grows."""
    if policy != DEFAULT_POLICY or not has_oversampler(estimator):
        return False
    values, counts = np.unique(np.asarray(y), return_counts=True)
    return len(values) > 1 and values[np.argmax(counts)] == target


def _rows(X, indices):
    return X[indices]


def _stack(X, extra):
    if scipy_sparse.issparse(X):
        return scipy_sparse.vstack([X, extra]).tocsr()
    return np.vstack([np.asarray(X), np.asarray(extra)])


def _clean_smote(X, y, flip_mask, rng, k=SMOTE_NEIGHBOURS):
    """SMOTE from unflipped rows only; returns (X, y, synthetic, fallback)."""
    from sklearn.neighbors import NearestNeighbors
    values, counts = np.unique(y, return_counts=True)
    top = counts.max()
    new_rows, new_labels = [], []
    for value, count in zip(values, counts):
        needed = int(top - count)
        if needed <= 0:
            continue
        eligible = np.flatnonzero((y == value) & ~flip_mask)
        if len(eligible) < k + 1:
            return X, y, 0, True                  # too few clean rows: NONE, flagged
        base = _rows(X, eligible)
        neighbours = NearestNeighbors(n_neighbors=k + 1).fit(base).kneighbors(
            base, return_distance=False)[:, 1:]
        parents = rng.integers(0, len(eligible), size=needed)
        partners = neighbours[parents, rng.integers(0, k, size=needed)]
        gaps = rng.random(needed)
        a, b = base[parents], base[partners]
        if scipy_sparse.issparse(base):
            synthetic = a + scipy_sparse.diags(gaps) @ (b - a)
        else:
            synthetic = a + gaps[:, None] * (b - a)
        new_rows.append(synthetic)
        new_labels.append(np.full(needed, value, dtype=y.dtype))
    if not new_rows:
        return X, y, 0, False
    extra = scipy_sparse.vstack(new_rows) if scipy_sparse.issparse(X) else np.vstack(new_rows)
    return _stack(X, extra), np.concatenate([y] + new_labels), sum(map(len, new_labels)), False


def resample(policy: str, X, y, flip_mask, random_state):
    """The flipped training data resampled by ``policy`` (not PIPELINE).
    Returns (X, y, info) with info = {"synthetic": n, "fallback": bool}."""
    y = np.asarray(y)
    flip_mask = np.asarray(flip_mask, dtype=bool)
    if policy == "NONE":
        return X, y, {"synthetic": 0, "fallback": False}
    if policy == "SMOTE":
        from imblearn.over_sampling import SMOTE
        values, counts = np.unique(y, return_counts=True)
        if counts.min() < SMOTE_NEIGHBOURS + 1:
            return X, y, {"synthetic": 0, "fallback": True}
        X_res, y_res = SMOTE(k_neighbors=SMOTE_NEIGHBOURS, random_state=random_state).fit_resample(X, y)
        return X_res, np.asarray(y_res), {"synthetic": int(len(y_res) - len(y)), "fallback": False}
    if policy == "CLEAN_SMOTE":
        X_res, y_res, synthetic, fallback = _clean_smote(
            X, y, flip_mask, np.random.default_rng(random_state))
        return X_res, y_res, {"synthetic": int(synthetic), "fallback": bool(fallback)}
    if policy == "UNDER":
        from imblearn.under_sampling import RandomUnderSampler
        X_res, y_res = RandomUnderSampler(sampling_strategy="not minority",
                                          random_state=random_state).fit_resample(X, y)
        return X_res, np.asarray(y_res), {"synthetic": 0, "fallback": False}
    raise ValueError(f"unknown sampling policy: {policy}")
