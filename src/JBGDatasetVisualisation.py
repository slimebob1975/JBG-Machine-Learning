"""301d (asked 2026-11-24): a 2D picture of a sample of a dataset.

The rows are drawn from the dataset (``draw_sample``), the numeric columns are
standardised and the categorical columns one-hot encoded (text and date
columns are left out, decided 2026-11-24), K-means groups the rows on all the
prepared columns, and PCA, t-SNE or MDS places them in two dimensions. The
browser draws the points (classes and clusters as colour and shape) and shows
each row's values on hover.

The same settings and data always give the same picture (a fixed seed).
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

METHODS = ("pca", "tsne", "mds")
SAMPLINGS = ("stratified", "random", "first")      # stratified is the default
SAMPLE_MIN, SAMPLE_MAX, SAMPLE_DEFAULT = 100, 3000, 1000
CLUSTERS_MAX = 8                                    # one marker shape per cluster
MDS_MAX = 2000      # MDS grows with the square of the rows: 3000 rows took over a minute
SEED = 42
OUTLIERS = ("none", "iforest", "lof")               # 301g: as a choice in the form
OUTLIER_SHARE_MIN, OUTLIER_SHARE_MAX, OUTLIER_SHARE_DEFAULT = 0.5, 10.0, 2.0   # percent
GRID = (120, 90)                                    # 301g: where boundaries are traced
HOVER_COLUMNS = 12                                  # values shown per point
MISSING = ""


class VisualisationRefused(ValueError):
    """The dataset or the settings do not allow a picture (the message says why)."""


def check_settings(method: str, clusters: int, sample_size: int, sampling: str,
                   outliers: str = "none", outlier_share: float = OUTLIER_SHARE_DEFAULT) -> None:
    if method not in METHODS:
        raise VisualisationRefused("method")
    if sampling not in SAMPLINGS:
        raise VisualisationRefused("sampling")
    if not 0 <= int(clusters) <= CLUSTERS_MAX:
        raise VisualisationRefused("clusters")
    if not SAMPLE_MIN <= int(sample_size) <= SAMPLE_MAX:
        raise VisualisationRefused("sample_size")
    if method == "mds" and int(sample_size) > MDS_MAX:
        raise VisualisationRefused("mds_sample_size")
    if outliers not in OUTLIERS:
        raise VisualisationRefused("outliers")
    if not OUTLIER_SHARE_MIN <= float(outlier_share) <= OUTLIER_SHARE_MAX:
        raise VisualisationRefused("outlier_share")


def draw_sample(frame: pd.DataFrame, size: int, sampling: str, class_column: str | None,
                seed: int = SEED) -> pd.DataFrame:
    """At most ``size`` rows: the first rows, a random sample, or a random sample
    with the same share of each class (rows without a class form a group of their
    own). For CSV files; SQL tables are sampled in the query."""
    if len(frame) <= size:
        return frame.reset_index(drop=True)
    if sampling == "first":
        return frame.head(size).reset_index(drop=True)
    if sampling == "random" or not class_column or class_column not in frame:
        return frame.sample(n=size, random_state=seed).reset_index(drop=True)
    fraction = size / len(frame)
    groups = frame[class_column].fillna(MISSING).astype(str)
    parts = [part.sample(n=max(1, int(round(len(part) * fraction))), random_state=seed)
             for _, part in frame.groupby(groups, sort=True)]
    sample = pd.concat(parts)
    if len(sample) > size:                    # rounding up in many small classes
        sample = sample.sample(n=size, random_state=seed)
    return sample.sort_index().reset_index(drop=True)


def prepare(frame: pd.DataFrame, numeric: list, categorical: list) -> np.ndarray:
    """Numeric columns standardised (missing values as the median), categorical
    columns one-hot encoded (missing as a category of its own)."""
    parts = []
    if numeric:
        values = frame[numeric].apply(lambda c: pd.to_numeric(c, errors="coerce")).astype(float)
        values = values.fillna(values.median()).fillna(0.0)
        spread = values.std(ddof=0).replace(0.0, 1.0)
        parts.append(((values - values.mean()) / spread).to_numpy())
    if categorical:
        texts = frame[categorical].astype(object).where(frame[categorical].notna(), MISSING)
        parts.append(pd.get_dummies(texts.astype(str), dtype=float).to_numpy())
    if not parts:
        raise VisualisationRefused("no_features")
    return np.hstack(parts)


def project(X: np.ndarray, method: str, seed: int = SEED) -> tuple[np.ndarray, list | None]:
    """Two coordinates per row, and for PCA the share of the variance each axis
    explains."""
    if X.shape[1] < 2:                       # one prepared column: it is the picture
        column = X[:, 0] if X.shape[1] else np.zeros(len(X))
        return np.column_stack([column, np.zeros(len(X))]), ([1.0, 0.0] if method == "pca" else None)
    if method == "pca":
        from sklearn.decomposition import PCA
        model = PCA(n_components=2, random_state=seed)
        coordinates = model.fit_transform(X)
        return coordinates, [float(v) for v in model.explained_variance_ratio_]
    if method == "tsne":
        from sklearn.manifold import TSNE
        perplexity = float(min(30, max(5, (len(X) - 1) // 3)))
        return TSNE(n_components=2, perplexity=perplexity, init="pca", random_state=seed
                    ).fit_transform(X), None
    from sklearn.manifold import MDS
    return MDS(n_components=2, n_init=1, max_iter=300, random_state=seed
               ).fit_transform(X), None


def clusters_for(X: np.ndarray, clusters: int, seed: int = SEED) -> list | None:
    if not clusters:
        return None
    from sklearn.cluster import KMeans
    k = max(1, min(int(clusters), len(X)))
    return [int(label) for label in KMeans(n_clusters=k, n_init=10, random_state=seed).fit_predict(X)]


def outlier_scores(X: np.ndarray, method: str, seed: int = SEED) -> np.ndarray | None:
    """301g: how unusual each row is, on all the prepared columns (higher is
    more unusual): Isolation Forest (how easily a row is split off) or Local
    Outlier Factor (how much sparser a row's surroundings are than its
    neighbours')."""
    if method == "iforest":
        from sklearn.ensemble import IsolationForest
        return -IsolationForest(n_estimators=200, random_state=seed).fit(X).score_samples(X)
    if method == "lof":
        from sklearn.neighbors import LocalOutlierFactor
        model = LocalOutlierFactor(n_neighbors=min(20, len(X) - 1))
        model.fit(X)
        return -model.negative_outlier_factor_
    return None


def marked_outliers(scores: np.ndarray, share: float) -> np.ndarray:
    """The share (percent) of rows with the highest scores, at least one."""
    count = max(1, int(round(len(scores) * float(share) / 100.0)))
    marked = np.zeros(len(scores), dtype=bool)
    marked[np.argsort(-scores, kind="stable")[:count]] = True
    return marked


def cluster_boundaries(coordinates: np.ndarray, groups: list, seed: int = SEED) -> list:
    """301g: dashed lines between the K-means clusters, traced in the picture.
    A nearest-neighbour classifier learns the clusters from the 2D points, and
    for each pair of clusters a contour is drawn where the two are equally
    likely, on the part of the picture where they are the two likeliest. The
    lines show the picture, not the data: in t-SNE and MDS the distances are
    distorted."""
    import contourpy
    from sklearn.neighbors import KNeighborsClassifier
    labels = np.asarray(groups)
    found = np.unique(labels)
    if len(found) < 2 or len(labels) < 10:
        return []
    low, high = coordinates.min(axis=0), coordinates.max(axis=0)
    spread = np.where(high - low > 0, high - low, 1.0)
    scaled = (coordinates - low) / spread
    model = KNeighborsClassifier(n_neighbors=min(25, len(labels) - 1), weights="distance")
    model.fit(scaled, labels)
    gx = np.linspace(0.0, 1.0, GRID[0])
    gy = np.linspace(0.0, 1.0, GRID[1])
    mesh_x, mesh_y = np.meshgrid(gx, gy)
    proba = model.predict_proba(np.column_stack([mesh_x.ravel(), mesh_y.ravel()]))
    proba = proba.reshape(GRID[1], GRID[0], len(model.classes_))
    order = np.argsort(-proba, axis=2)
    top, second = order[:, :, 0], order[:, :, 1]
    lines = []
    for a in range(len(model.classes_)):
        for b in range(a + 1, len(model.classes_)):
            pair = ((top == a) & (second == b)) | ((top == b) & (second == a))
            if not pair.any():
                continue
            field = np.ma.masked_array(proba[:, :, a] - proba[:, :, b], mask=~pair)
            generator = contourpy.contour_generator(gx, gy, field)
            for line in generator.lines(0.0):
                if len(line) < 2:
                    continue
                points = low + np.asarray(line) * spread
                lines.append([[round(float(x), 5), round(float(y), 5)] for x, y in points])
    return lines


def _shown(value):
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return ""
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)[:80]


def visualise(frame: pd.DataFrame, *, id_column: str | None, class_column: str | None,
              numeric: list, categorical: list, method: str, clusters: int,
              outliers: str = "none", outlier_share: float = OUTLIER_SHARE_DEFAULT,
              boundaries: bool = False, seed: int = SEED) -> dict:
    """The picture's points and what the browser needs to draw them."""
    numeric = [c for c in numeric if c in frame]
    categorical = [c for c in categorical if c in frame]
    if len(frame) < 3:
        raise VisualisationRefused("too_few_rows")
    X = prepare(frame, numeric, categorical)
    coordinates, explained = project(X, method, seed)
    groups = clusters_for(X, clusters, seed)
    scores = outlier_scores(X, outliers, seed)
    marked = marked_outliers(scores, outlier_share) if scores is not None else None
    lines = cluster_boundaries(coordinates, groups, seed) if boundaries and groups else []
    classes = (frame[class_column].astype(object).where(frame[class_column].notna(), None)
               if class_column and class_column in frame else None)
    hover = [c for c in [id_column, class_column] if c and c in frame]
    hover += [c for c in numeric + categorical if c not in hover][: HOVER_COLUMNS - len(hover)]
    points = []
    for i in range(len(frame)):
        label = None if classes is None else classes.iloc[i]
        points.append({"x": round(float(coordinates[i, 0]), 5), "y": round(float(coordinates[i, 1]), 5),
                       "class": None if label is None or str(label).strip() == "" else str(label),
                       "cluster": None if groups is None else groups[i],
                       "outlier": None if marked is None else bool(marked[i]),
                       "outlier_score": None if scores is None else round(float(scores[i]), 4),
                       "values": [_shown(frame[c].iloc[i]) for c in hover]})
    found = sorted({p["class"] for p in points if p["class"] is not None})
    return {"method": method, "rows": len(frame), "points": points, "hover_columns": hover,
            "classes": found, "unclassified": sum(p["class"] is None for p in points),
            "clusters": 0 if groups is None else max(groups) + 1,
            "explained": explained, "features": {"numeric": numeric, "categorical": categorical},
            "outliers": outliers, "outlier_count": 0 if marked is None else int(marked.sum()),
            "boundaries": lines,
            "columns_used": X.shape[1]}
