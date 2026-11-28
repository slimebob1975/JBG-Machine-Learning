"""301v (asked 2026-11-27): the final model's pipeline, step by step with its
parameters, saved next to a run's results, so exports can say exactly which
pipeline produced them, tuned parameters included."""
from __future__ import annotations

import json
import math
from pathlib import Path

SIMPLE = (bool, int, float, str, type(None))
# Steps that do nothing (no scaling, no over- or undersampling, no reduction):
# kept in the description, left out of the one-line summary.
PASS_THROUGH = {"NOS", "NOG", "NUG", "NOR"}


def _value(value):
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, SIMPLE):
        return value
    if isinstance(value, (list, tuple)) and all(isinstance(v, SIMPLE) for v in value):
        return list(value)
    if callable(value) and hasattr(value, "__name__"):
        return value.__name__
    name = type(value).__name__
    return name if name not in ("dict",) else str(value)[:200]


def describe(model) -> list:
    """The steps of a pipeline (or one estimator): name, class and parameters
    (those that are not sub-estimators; sub-estimators are named by class)."""
    steps = getattr(model, "steps", None) or [("model", model)]
    described = []
    for name, step in steps:
        if step is None or step == "passthrough":
            continue
        try:
            params = step.get_params(deep=False)
        except Exception:
            params = {}
        described.append({"step": str(name), "class": type(step).__name__,
                          "params": {str(k): _value(v) for k, v in sorted(params.items())}})
    return described


def write(config, model) -> Path | None:
    """Saved as ``final_pipeline_...json`` beside the run's other results."""
    try:
        path = Path(config.get_output_filepath("final_pipeline"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"version": 1, "steps": describe(model)}, ensure_ascii=False,
                                   indent=2), encoding="utf-8")
        return path
    except Exception:
        return None


def summary(steps: list) -> str:
    """One line: each step's class with its most telling parameters."""
    keep = ("C", "alpha", "n_estimators", "max_depth", "learning_rate", "n_neighbors",
            "k_neighbors", "kernel", "n_components", "penalty", "solver", "max_iter",
            "hidden_layer_sizes", "iterations", "depth", "l2_leaf_reg")
    parts = []
    for step in steps or []:
        if step.get("step") in PASS_THROUGH:                 # "no scaling" and the like
            continue
        shown = [f"{k}={step['params'][k]}" for k in keep if k in step.get("params", {})
                 and step["params"][k] is not None]
        parts.append(step["class"] + (f"({', '.join(shown)})" if shown else ""))
    return " · ".join(parts)
