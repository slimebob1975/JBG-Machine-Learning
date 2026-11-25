"""300w (2026-11-24): Average Precision scored on the model's probabilities.

Average Precision ranks rows by how strongly the model believes in a class, so
it needs probabilities (or decision values), not the predicted classes. The
scorer built by ``make_scorer`` scored hard predictions, and with scikit-learn
1.9 it also refused text classes. This scorer works with any class labels:

- two classes: the positive class is the configuration's Dark Numbers target
  if one is chosen, otherwise the smallest class (as in the feature
  investigation, 299i). ``JBGHandler`` sets it from the training labels;
  without it, the smallest class in the scored labels is used;
- more than two classes: the micro, macro or weighted average over each class
  against the rest, so no positive class is needed.

Models without ``predict_proba`` are scored on ``decision_function``. The class
is defined at module level so that it pickles with saved models."""
from __future__ import annotations

from collections import Counter

import numpy as np
from sklearn.metrics import average_precision_score
from sklearn.preprocessing import label_binarize


def smallest_class(labels):
    """The least frequent label; ties go to the first in text order."""
    counts = Counter(np.asarray(labels).reshape(-1).tolist())
    return min(counts, key=lambda value: (counts[value], str(value)))


class AveragePrecisionScorer:
    """A scorer ``(estimator, X, y) -> float`` for cross-validation and search."""

    def __init__(self, average: str = "macro", positive_class=None) -> None:
        self.average = average
        self.positive_class = positive_class

    def for_positive_class(self, positive_class) -> "AveragePrecisionScorer":
        return AveragePrecisionScorer(self.average, positive_class)

    def __repr__(self) -> str:
        return f"AveragePrecisionScorer(average={self.average!r}, positive_class={self.positive_class!r})"

    def __call__(self, estimator, X, y) -> float:
        y = np.asarray(y).reshape(-1)
        classes = list(getattr(estimator, "classes_", np.unique(y)))
        if hasattr(estimator, "predict_proba"):
            scores, kind = np.asarray(estimator.predict_proba(X)), "proba"
        else:
            scores, kind = np.asarray(estimator.decision_function(X)), "decision"
        if len(classes) == 2:
            positive = self.positive_class
            if positive is None or not any(str(c) == str(positive) for c in classes):
                positive = smallest_class(y)
            index = next(i for i, c in enumerate(classes) if str(c) == str(positive))
            if scores.ndim == 1:                      # a decision value for classes[1]
                column = scores if index == 1 else -scores
            else:
                column = scores[:, index]
            truth = np.array([str(value) == str(positive) for value in y])
            if not truth.any():
                return 0.0
            return float(average_precision_score(truth, column))
        truth = label_binarize(y, classes=classes)
        if scores.ndim == 1 or scores.shape[1] != len(classes):
            raise ValueError(f"{kind} scores do not match the {len(classes)} classes")
        present = truth.any(axis=0)                  # classes with rows in this part
        return float(average_precision_score(truth[:, present], scores[:, present],
                                             average=self.average))
