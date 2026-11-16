"""Key figures and chart series for the Overview tab (revision 299k).

Agreed 2026-11-13 (mockup): all the user's projects at the top, each figure
with "of which in the open project"; the open project below. Built from the
owner's own run records only (deleted runs are left out); numbers only, no
class names or row values. Rows processed and models compared are recorded by
the worker when a run finishes (299k), so older runs count as 0 and the
charts fill in from new runs onward.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

WEEKS = 12
QUALITY_RUNS = 20
# The configuration's scoring metric -> the stored evaluation's field. Micro
# averages equal accuracy; metrics the evaluation does not keep fall back to MCC.
QUALITY_FIELDS = {
    "accuracy": "accuracy", "balanced_accuracy": "balanced_accuracy", "mcc": "mcc",
    "f1_macro": "f1_macro", "f1_weighted": "f1_weighted", "recall_macro": "recall_macro",
    "recall_weighted": "recall_weighted", "precision_macro": "precision_macro",
    "precision_weighted": "precision_weighted", "f1_micro": "accuracy",
    "recall_micro": "accuracy", "precision_micro": "accuracy",
}
QUALITY_LABELS = {
    "accuracy": "Accuracy", "balanced_accuracy": "Balanced accuracy", "mcc": "MCC",
    "f1_macro": "F1 (macro)", "f1_weighted": "F1 (weighted)", "recall_macro": "Recall (macro)",
    "recall_weighted": "Recall (weighted)", "precision_macro": "Precision (macro)",
    "precision_weighted": "Precision (weighted)",
}


def _meta(record) -> dict:
    meta = record.spec.get("project_run") if isinstance(record.spec, dict) else None
    return meta if isinstance(meta, dict) else {}


def _count(result, name) -> int:
    counts = result.get("counts") if isinstance(result, dict) else None
    value = counts.get(name) if isinstance(counts, dict) else None
    return value if type(value) is int and 0 <= value <= 2**53 else 0


def _quality(record):
    """(field, value) of the run's configured metric, or None."""
    result = record.result if isinstance(record.result, dict) else {}
    evaluation = result.get("evaluation")
    if not isinstance(evaluation, dict):
        return None
    configuration = record.spec.get("configuration") if isinstance(record.spec, dict) else None
    mode = configuration.get("mode") if isinstance(configuration, dict) else None
    scoring = mode.get("scoring") if isinstance(mode, dict) else None
    name = QUALITY_FIELDS.get(scoring, "mcc")
    value = evaluation.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return name, float(value)


def _week_start(moment: datetime) -> datetime:
    moment = moment.astimezone(timezone.utc)
    day = moment - timedelta(days=moment.weekday())
    return day.replace(hour=0, minute=0, second=0, microsecond=0)


def _weeks(now: datetime) -> list:
    first = _week_start(now) - timedelta(weeks=WEEKS - 1)
    return [first + timedelta(weeks=i) for i in range(WEEKS)]


def overview_stats(records, *, project_names: dict, open_project: str | None,
                   models_in_use: dict, now: datetime | None = None) -> dict:
    """The Overview's figures from the owner's run records.

    ``project_names``: project ID -> name (the owner's projects); runs of
    other projects are left out. ``models_in_use``: project ID -> number of
    available models."""
    now = now or datetime.now(timezone.utc)
    weeks = _weeks(now)
    index = {week: i for i, week in enumerate(weeks)}
    runs = [r for r in records if _meta(r).get("project_id") in project_names]
    finished = [r for r in runs if r.status.value in ("succeeded", "failed", "interrupted",
                                                       "cancelled")]

    def figures(scope):
        training = [r for r in scope if _meta(r).get("kind", "training") == "training"
                    and r.status.value == "succeeded"]
        return {"training_runs": len(training),
                "rows": sum(_count(r.result, "rows") for r in scope
                            if r.status.value == "succeeded"),
                "models": sum(_count(r.result, "models") for r in training)}

    mine = [r for r in runs if _meta(r).get("project_id") == open_project]
    totals, opened = figures(runs), figures(mine)
    totals["in_use"] = sum(models_in_use.values())
    opened["in_use"] = models_in_use.get(open_project, 0)

    per_week = [{"week": w, "succeeded": 0, "failed": 0} for w in weeks]
    for record in finished:
        at = index.get(_week_start(record.created_at))
        if at is not None:
            per_week[at]["succeeded" if record.status.value == "succeeded" else "failed"] += 1

    rows_by_project = {pid: 0 for pid in project_names}
    for record in runs:
        if record.status.value == "succeeded":
            rows_by_project[_meta(record)["project_id"]] += _count(record.result, "rows")
    per_project = sorted(({"project_id": pid, "name": project_names[pid], "rows": rows,
                           "open": pid == open_project}
                          for pid, rows in rows_by_project.items()),
                         key=lambda item: (-item["rows"], item["name"].lower()))

    quality, rows_per_week, latest = [], [{"week": w, "rows": 0} for w in weeks], []
    if open_project is not None:
        trained = sorted((r for r in mine if _meta(r).get("kind", "training") == "training"
                          and r.status.value == "succeeded"), key=lambda r: r.created_at)
        for record in trained:
            found = _quality(record)
            if found is not None:
                quality.append({"run_id": record.run.key, "created_at": record.created_at,
                                "metric": found[0], "value": found[1]})
        quality = quality[-QUALITY_RUNS:]
        for record in mine:
            at = index.get(_week_start(record.created_at))
            if at is not None and record.status.value == "succeeded":
                rows_per_week[at]["rows"] += _count(record.result, "rows")
        latest = sorted(mine, key=lambda r: r.created_at, reverse=True)[:5]
    recent = [q["value"] for q in quality[-3:]]
    metrics = {q["metric"] for q in quality}
    return {"totals": totals, "open": opened, "per_week": per_week, "per_project": per_project,
            "quality": quality, "quality_average": (sum(recent) / len(recent)) if recent else None,
            "quality_metric": metrics.pop() if len(metrics) == 1 else ("mcc" if not metrics else ""),
            "rows_per_week": rows_per_week,
            "latest": [{"run_id": r.run.key, "kind": _meta(r).get("kind", "training"),
                        "status": r.status.value, "created_at": r.created_at,
                        "configuration_name": _meta(r).get("configuration_name"),
                        "configuration_version": _meta(r).get("configuration_version")}
                       for r in latest]}
