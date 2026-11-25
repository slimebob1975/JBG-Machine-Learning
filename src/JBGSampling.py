"""Compatible sampling selections; fitted models retain one enum per sampler."""

from collections import Counter


def partial_undersampling_counts(y, majority_multiple):
    """Cap each class at a multiple of the smallest training-fold class.

    Never remove minority rows or request additional rows when a fold is
    already less imbalanced than the requested profile. For multiclass data,
    the same cap applies independently to every class. This top-level callable
    can be cloned/pickled with the pipeline for CV workers and saved models.
    """
    if isinstance(majority_multiple, bool) or not isinstance(majority_multiple, int) or majority_multiple < 1:
        raise ValueError("majority_multiple must be a positive integer")
    counts = Counter(y)
    if not counts:
        raise ValueError("Partial undersampling requires nonempty training labels")
    cap = min(counts.values()) * majority_multiple
    return {label: min(count, cap) for label, count in counts.items()}


def sampling_names(value, enum_type, fallback):
    """Normalize old scalar names/enums and new nonempty selections in stable order."""
    if value is None:
        value = [fallback]
    elif isinstance(value, str):
        value = value.split(",")
    elif isinstance(value, enum_type):
        value = [value]
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError(f"Select at least one {enum_type.__name__} method (including no sampling).")
    names = []
    for item in value:
        try:
            name = item.name if isinstance(item, enum_type) else str(item).strip()
            enum_type[name]
        except (KeyError, TypeError) as error:
            raise ValueError(f"Unsupported {enum_type.__name__} method: {item}") from error
        if name not in names:
            names.append(name)
    return names


def categorical_feature_indices(feature_names, categorical_names):
    """Resolve fitted categorical feature names to stable converted-column indices.

    Ordinary JBG conversion turns categorical text into ordinal numeric columns, so
    dtype-based sampler auto-detection cannot recover their semantics later.
    """
    names = list(feature_names)
    if len(names) != len(set(names)):
        raise ValueError("Categorical SMOTE requires unique converted feature names.")

    categories = tuple(categorical_names or ())
    if len(categories) != len(set(categories)):
        raise ValueError("Categorical SMOTE received duplicate fitted categorical feature names.")

    missing = [name for name in categories if name not in names]
    if missing:
        raise ValueError(
            "Categorical SMOTE contract is inconsistent: "
            f"{len(missing)} fitted categorical column(s) are absent after conversion."
        )

    selected = set(categories)
    return tuple(index for index, name in enumerate(names) if name in selected)


def validate_categorical_oversampling(method_name, categorical_indices, n_features):
    """Validate the converted-feature contract for SMOTE-NC or SMOTE-N.

    Returns a normalized tuple of categorical indices. The caller can pass the SMOTE-NC
    result directly to ``categorical_features``. SMOTE-N is accepted only when every
    converted feature is explicitly known to be categorical.
    """
    if isinstance(n_features, bool) or not isinstance(n_features, int) or n_features < 1:
        raise ValueError("Categorical SMOTE requires a positive converted feature count.")

    indices = tuple(categorical_indices or ())
    invalid = [
        index for index in indices
        if isinstance(index, bool) or not isinstance(index, int)
        or index < 0 or index >= n_features
    ]
    if invalid or len(set(indices)) != len(indices):
        raise ValueError("Categorical SMOTE received an invalid converted-feature index contract.")

    method_name = str(method_name).upper()
    if method_name == "SNC":
        if not indices:
            raise ValueError(
                "SMOTE-NC requires fitted categorical feature roles; no categorical converted "
                "features were identified. Configure categorical text columns or use a numerical "
                "oversampler."
            )
        if len(indices) >= n_features:
            raise ValueError(
                "SMOTE-NC requires both categorical and non-categorical converted features; "
                "use SMOTE-N only for an all-categorical representation."
            )
    elif method_name == "SNN":
        if tuple(sorted(indices)) != tuple(range(n_features)):
            raise ValueError(
                "SMOTE-N requires every converted predictor to be categorical. The fitted "
                "representation contains non-categorical features; use SMOTE-NC or another "
                "oversampler."
            )
    else:
        raise ValueError(f"Unsupported categorical oversampler contract: {method_name}")

    return indices


# --- 301a: the share sliders (specified 2026-11-24) -------------------------------------
# The oversampling slider sets the smallest class's share of all rows after
# sampling, raised towards 50 %. The undersampling slider sets the largest
# class's share, lowered towards 50 %. Shares are stored in percent.

OVERSAMPLERS_WITH_SHARE = frozenset({"RND", "SME", "SNC", "SNN", "ADA", "BRD", "KMS", "SVM"})
# The cleaning undersamplers (CNN, ENN, RNN, AKN, NCR, OSS, TKL) choose rows by
# their own rules and take no share.
UNDERSAMPLERS_WITH_SHARE = frozenset({"RND", "CCS", "IHT", "NMS"})

# 301a: the removed presets kept the majority at most k times the smallest class.
# With two classes that is a largest-class share of k / (k + 1).
UNDERSAMPLING_PRESETS = {"R02": 2, "R05": 5, "R10": 10, "R20": 20}


def _smallest(counts):
    return min(counts, key=lambda label: (counts[label], str(label)))


def _largest(counts):
    return max(counts, key=lambda label: (counts[label], str(label)))


def share_counts(y, share, role):
    """The ``sampling_strategy`` for a share slider: the class count to sample
    to, so that the smallest class (``role="over"``) or the largest class
    (``role="under"``) makes up ``share`` percent of the rows. A class already
    at or beyond the share is left as it is. A top-level function, used with
    ``functools.partial``, so pipelines with it pickle."""
    counts = Counter(y)
    if len(counts) < 2:
        return {}
    fraction = min(max(float(share) / 100.0, 1e-6), 1 - 1e-6)
    total = sum(counts.values())
    if role == "over":
        label = _smallest(counts)
        rest = total - counts[label]
        return {label: max(counts[label], int(round(fraction * rest / (1 - fraction))))}
    if role == "under":
        label = _largest(counts)
        rest = total - counts[label]
        return {label: min(counts[label], max(1, int(round(fraction * rest / (1 - fraction)))))}
    raise ValueError(f"Unknown sampling role: {role!r}")


def class_shares(counts) -> dict:
    """The smallest and the largest class's share in percent, and the standard
    values (agreed 2026-11-24): oversampling raises the smallest class to the
    next larger class's share, undersampling lowers the largest class to the
    next smaller class's share, both stopping at 50 %."""
    counts = {label: int(count) for label, count in dict(counts).items() if int(count) > 0}
    if len(counts) < 2:
        return {}
    total = sum(counts.values())
    shares = sorted(100.0 * count / total for count in counts.values())
    return {"smallest": shares[0], "largest": shares[-1],
            "standard_over": min(50.0, shares[1]), "standard_under": max(50.0, shares[-2])}


def share_unchanged(share, shares: dict, role: str, tolerance: float = 0.05) -> bool:
    """True when the slider would change nothing: no share, or a share at or
    beyond the class's current share."""
    if share is None:
        return True
    if role == "over":
        return float(share) <= shares["smallest"] + tolerance
    return float(share) >= shares["largest"] - tolerance


def convert_undersampling_presets(mode: dict) -> dict:
    """301a: the undersampling presets R02-R20 are removed from the choices. A
    stored configuration that uses them gets Random undersampling and, unless a
    share is already set, the largest-class share of the most balancing preset
    chosen (R02 gives 66.7 %)."""
    mode = dict(mode or {})
    listed = list(mode.get("undersamplers") or [])
    single = mode.get("undersampler")
    found = [code for code in listed + [single] if code in UNDERSAMPLING_PRESETS]
    if not found:
        return mode
    if listed:
        converted = []
        for code in listed:
            code = "RND" if code in UNDERSAMPLING_PRESETS else code
            if code not in converted:
                converted.append(code)
        mode["undersamplers"] = converted
    if single in UNDERSAMPLING_PRESETS:
        mode["undersampler"] = "RND"
    if mode.get("undersampling_share") is None:
        k = min(UNDERSAMPLING_PRESETS[code] for code in found)
        mode["undersampling_share"] = round(100.0 * k / (k + 1), 1)
    return mode


def share_notes(mode, labels) -> list:
    """301a: what the run log says about the share sliders for these training
    labels: a share the class has already reached (the sampling changes
    nothing in this run), and chosen methods that take no share."""
    from JBGMeta import Oversampling, Undersampling
    shares = class_shares(Counter(labels))
    notes = []
    for role, enum_type, fallback, uses, attribute in (
            ("over", Oversampling, getattr(mode, "oversampler", Oversampling.NOG),
             OVERSAMPLERS_WITH_SHARE, "oversampling_share"),
            ("under", Undersampling, getattr(mode, "undersampler", Undersampling.NUG),
             UNDERSAMPLERS_WITH_SHARE, "undersampling_share")):
        share = getattr(mode, attribute, None)
        listed = getattr(mode, role + "samplers", None)
        try:
            chosen = sampling_names(listed, enum_type, fallback)
        except ValueError:
            continue
        with_share = [name for name in chosen if name in uses]
        without = [name for name in chosen if name not in uses and name not in ("NOG", "NUG")]
        word = "oversampling" if role == "over" else "undersampling"
        if share is not None and with_share and shares and share_unchanged(share, shares, role, 0.0):
            which = "smallest" if role == "over" else "largest"
            notes.append(f"The {which} class is already at {shares[which]:.1f} %, so the "
                         f"{word} share {float(share):.1f} % changes nothing in this run.")
        if share is not None and without:
            notes.append(f"These {word} methods take no share and use their own rules: "
                         f"{', '.join(without)}.")
    return notes
