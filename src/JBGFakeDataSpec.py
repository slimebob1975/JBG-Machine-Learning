"""301o (asked 2026-11-26): a specification of a dataset for generating fake data.

A JSON description from which a generator can make data that looks like the
dataset, without any real row in it (decided 2026-11-26):

- per column: role, type, missing share and its distribution (numbers as
  quantiles, mean and spread; categories as shares; dates as quantiles; free
  text only as lengths, never its content);
- the same distributions per class, so fake data keeps the differences between
  the classes;
- correlations between the numeric columns;
- rare values and combinations, under 0.1 % of the rows, are merged into
  "Övrigt" (OTHER), and numbers get quantiles from 0.1 % to 99.9 % instead of
  their exact minimum and maximum, so single rows do not show.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone

import numpy as np
import pandas as pd

SCHEMA = "jbg-fake-data-spec"
VERSION = 1
RARE_SHARE = 0.001                      # 0.1 % of the rows (decided 2026-11-26)
OTHER = "Övrigt"
QUANTILES = (0.001, 0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99, 0.999)
CATEGORY_TYPES = ("categorical", "class")


def _number(value):
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return round(value, 6) if math.isfinite(value) else None


def _numbers(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _present(series: pd.Series) -> pd.Series:
    text = series.astype(object).where(series.notna(), None)
    return text[text.map(lambda v: v is not None and str(v).strip() != "")]


def _infer_type(series: pd.Series, categorical_limit: int = 30) -> str:
    present = _present(series)
    if present.empty:
        return "categorical"
    numbers = _numbers(present)
    if numbers.notna().mean() > 0.98:
        return "numeric"
    return "categorical" if present.astype(str).nunique() <= categorical_limit else "text"


def _numeric_summary(series: pd.Series) -> dict:
    values = _numbers(series).dropna()
    if values.empty:
        return {"count": 0}
    quantiles = values.quantile(list(QUANTILES))
    return {"count": int(len(values)),
            "integer": bool(np.all(np.mod(values, 1) == 0)),
            "mean": _number(values.mean()), "std": _number(values.std(ddof=0)),
            "quantiles": {f"{q:g}": _number(quantiles.loc[q]) for q in QUANTILES}}


def _date_summary(series: pd.Series) -> dict:
    values = pd.to_datetime(_present(series), errors="coerce").dropna()
    if values.empty:
        return {"count": 0}
    ordinal = values.map(lambda v: v.value)
    quantiles = ordinal.quantile(list(QUANTILES))
    return {"count": int(len(values)),
            "quantiles": {f"{q:g}": pd.Timestamp(int(quantiles.loc[q])).date().isoformat()
                          for q in QUANTILES}}


def _text_summary(series: pd.Series) -> dict:
    present = _present(series).astype(str)
    if present.empty:
        return {"count": 0}
    lengths = present.str.len()
    words = present.str.split().map(len)
    return {"count": int(len(present)),
            "distinct_share": _number(present.nunique() / len(present)),
            "length": {f"{q:g}": _number(lengths.quantile(q)) for q in QUANTILES},
            "words": {f"{q:g}": _number(words.quantile(q)) for q in QUANTILES}}


def _category_summary(series: pd.Series, all_rows: int) -> dict:
    """Shares of the values; values seen in fewer than 0.1 % of all the rows
    are merged into OTHER."""
    present = _present(series).astype(str)
    if present.empty:
        return {"count": 0, "values": []}
    counts = present.value_counts()
    floor = RARE_SHARE * all_rows
    kept = counts[counts >= floor]
    other = int(counts[counts < floor].sum())
    values = [{"value": str(v), "share": _number(c / len(present))} for v, c in kept.items()]
    if other:
        values.append({"value": OTHER, "share": _number(other / len(present))})
    return {"count": int(len(present)), "values": values,
            "merged_values": int((counts < floor).sum())}


def _summary(series: pd.Series, kind: str, all_rows: int) -> dict:
    missing = 1.0 - (len(_present(series)) / len(series)) if len(series) else 0.0
    if kind == "numeric":
        found = _numeric_summary(series)
    elif kind == "date":
        found = _date_summary(series)
    elif kind == "text":
        found = _text_summary(series)
    elif kind in CATEGORY_TYPES:
        found = _category_summary(series, all_rows)
    else:
        found = {}
    return dict(found, missing_share=_number(missing))


def build_spec(frame: pd.DataFrame, *, roles: dict, class_column: str | None,
               dataset_name: str, source: str, rows_total: int,
               categorical_limit: int = 30) -> dict:
    """The specification. ``roles`` maps a column to its role (id, class,
    numeric, categorical, text, date, group, ignored); a column without a role
    gets a type from its values."""
    all_rows = len(frame)
    kinds = {}
    for column in frame.columns:
        role = roles.get(column)
        if role in ("numeric", "categorical", "text", "date"):
            kinds[column] = role
        elif role == "class":
            kinds[column] = "class"
        elif role in ("id", "group", "ignored"):
            kinds[column] = role
        else:
            kinds[column] = _infer_type(frame[column], categorical_limit)
    classes = None
    if class_column and class_column in frame:
        classes = _present(frame[class_column]).astype(str)
    columns = []
    for column in frame.columns:
        kind = kinds[column]
        entry = {"name": str(column), "role": roles.get(column), "type": kind}
        if kind in ("id", "group", "ignored"):
            entry["note"] = {"id": "unique per row: generate a sequence",
                             "group": "rows of a group belong together",
                             "ignored": "not used by the model"}[kind]
            entry["missing_share"] = _summary(frame[column], "none", all_rows)["missing_share"]
            columns.append(entry)
            continue
        entry.update(_summary(frame[column], kind, all_rows))
        if classes is not None and kind != "class":
            # Per class: the same summary on the class's rows; rare values are
            # judged against all the rows, so small classes merge more.
            entry["by_class"] = {
                str(label): _summary(frame.loc[classes.index[classes == label], column],
                                     kind, all_rows)
                for label in sorted(classes.unique())}
        columns.append(entry)
    numeric = [c for c in frame.columns if kinds[c] == "numeric"]
    correlations = None
    if len(numeric) >= 2:
        matrix = frame[numeric].apply(_numbers).corr(min_periods=10)
        correlations = {"method": "pearson", "columns": [str(c) for c in numeric],
                        "matrix": [[_number(v) for v in row] for row in matrix.to_numpy()]}
    class_shares = None
    if classes is not None and not classes.empty:
        counts = classes.value_counts()
        class_shares = [{"value": str(v), "share": _number(c / len(classes))}
                        for v, c in counts.items()]
    return {"schema": SCHEMA, "version": VERSION,
            "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "dataset": dataset_name, "source": source,
            "rows": int(rows_total), "rows_used": int(all_rows),
            "sampled": bool(all_rows < rows_total),
            "rare_share": RARE_SHARE, "other": OTHER,
            "quantiles": [f"{q:g}" for q in QUANTILES],
            "class_column": class_column, "classes": class_shares,
            "columns": columns, "correlations": correlations}
