"""The feature investigation as a run of the web interface (revision 299i).

Agreed 2026-11-13: the investigation that Voila runs in its own interface
becomes a run kind ("investigation") of the durable runs: started on the
Training tab with the chosen dataset and configuration, run by a worker,
cancellable, its results in the run's own folder. The search itself is the
engine's (JBGFeatureSearchService.run_training_feature_search); it fits on
the training part only and never saves a model or predictions.

- The settings are the configuration's feature investigation settings.
- More than two classes: the target class against the rest (one_vs_rest).
- Progress: a stage marker and an inner bar of feature subsets evaluated; every
  search event is a cancel checkpoint.
- The full result (with column and class names) is written to the run folder
  as ``investigation.json``; the store gets numbers only.
"""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path

RESULT_FILE = "investigation.json"
STAGE = "feature_investigation"
INNER_DESCRIPTION = "Feature subsets"


def search_budget(mode) -> dict:
    """The search's size. A named preset (Quick, Standard, Extended) decides
    it, as choosing one does in Voila; Custom uses the configuration's values."""
    from JBGFeatureSearchPresets import PRESETS, preset_values
    if mode.feature_search_preset in PRESETS:
        return preset_values(mode.feature_search_preset)
    return dict(trials=mode.feature_search_trials, sizes=mode.feature_search_sizes,
                inner_folds=mode.feature_search_inner_folds,
                outer_folds=mode.feature_search_outer_folds,
                top_sets=mode.feature_search_top_sets,
                refine_rounds=mode.feature_search_refine_rounds,
                max_evaluations=mode.feature_search_max_evaluations,
                min_gain=mode.feature_search_min_gain)


def search_options(config):
    """The engine's SearchOptions from the configuration's investigation settings."""
    from JBGFeatureSearch import SearchOptions, resolve_feature_search_workers
    mode = config.mode
    budget = search_budget(mode)
    workers, _ = resolve_feature_search_workers(budget["max_evaluations"])
    return SearchOptions(
        trials=budget["trials"], sizes=tuple(budget["sizes"]),
        inner_folds=budget["inner_folds"], outer_folds=budget["outer_folds"],
        top_sets=budget["top_sets"], refine_rounds=budget["refine_rounds"],
        max_evaluations=budget["max_evaluations"],
        min_gain=budget["min_gain"], scaler=mode.feature_search_scaler,
        oversampling=mode.feature_search_oversampling, reduction=mode.feature_search_reduction,
        C=mode.feature_search_linear_c, max_iterations=mode.feature_search_linear_max_iterations,
        model_type=mode.feature_search_model_type,
        non_linear_max_iterations=mode.feature_search_non_linear_max_iterations,
        non_linear_alpha=mode.feature_search_non_linear_alpha,
        non_linear_hidden_layers=tuple(mode.feature_search_non_linear_hidden_layers),
        non_linear_learning_rate=mode.feature_search_non_linear_learning_rate,
        tree_estimator=mode.feature_search_tree_estimator,
        tree_n_estimators=mode.feature_search_tree_n_estimators,
        tree_max_depth=mode.feature_search_tree_max_depth or None,
        tree_min_samples_leaf=mode.feature_search_tree_min_samples_leaf,
        tree_class_weight=mode.feature_search_tree_class_weight,
        tree_positive_threshold=mode.feature_search_tree_positive_threshold,
        parallel_workers=workers,
        catboost_class_weight=mode.feature_search_catboost_class_weight,
        catboost_iterations=mode.feature_search_catboost_iterations)


def investigation_config(config):
    """A copy that trains only: no predictions, mispredictions, Dark Numbers
    or feature importance (as Voila's investigation does)."""
    run = copy.deepcopy(config)
    run.mode.train = True
    run.mode.predict = False
    run.mode.mispredicted = False
    run.mode.calculate_dark_numbers = False
    run.mode.calculate_feature_importance = False
    return run


class Progress:
    """Turn the search's events into the run's progress and cancel checks."""

    def __init__(self, observed) -> None:
        self._observed = observed
        self._scope = None

    def __call__(self, event: dict) -> None:
        kind = event.get("event")
        if kind == "candidate_completed":
            scope, total = event.get("scope"), event.get("max_evaluations")
            if scope != self._scope and isinstance(total, int) and total >= 1:
                if self._scope is not None:
                    self._observed.end_inline_progress("feature_investigation", set_100=False)
                self._scope = scope
                self._observed.start_inline_progress("feature_investigation", INNER_DESCRIPTION,
                                                     total, "")
            candidate = event.get("candidate")
            if isinstance(candidate, int):
                self._observed.update_inline_progress("feature_investigation", candidate, "")
        else:
            self._observed._inner_checkpoint()           # every event: cancel check


def _plain(value):
    """JSON-native values (the engine's results may hold numpy numbers)."""
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, (str, bool)) or value is None:
        return value
    if isinstance(value, int):
        return value
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return number if math.isfinite(number) else None


def summary(result: dict) -> dict:
    """Numbers only, for the run store (names stay in the run folder)."""
    def score(part):
        value = ((result.get("nested_validation") or {}).get(part) or {}).get("mean_mcc")
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) else None
    selected = (result.get("recommendation") or {}).get("selected_columns") or []
    original = result.get("original_columns") or []
    return {"schema_version": 1, "kind": "investigation",
            "selected_count": len(selected), "original_count": len(original),
            "selected_mcc": score("selected"), "baseline_mcc": score("full_baseline"),
            "one_vs_rest": "one_vs_rest" in result}


def run_investigation(record, config, observed, credentials, artifacts, folder: Path) -> dict:
    """Run the investigation of a claimed job; return the store summary."""
    from JBGApplicationContracts import DataSourceKind
    from JBGFeatureSearchService import run_training_feature_search
    run_config = investigation_config(config)
    observed.record_task_stage(STAGE)
    csv_source = None
    if record.source is DataSourceKind.CSV:
        from Storage.FileArtifactRepository import FileArtifactRepository
        from Storage.ArtifactContract import StorageScope
        if artifacts is None:
            raise ValueError("artifact repository path required for CSV jobs")
        csv = record.spec["csv"]
        csv_source = (FileArtifactRepository(artifacts),
                      StorageScope(csv["tenant_id"], csv["project_id"]), csv["configuration_id"])
    else:
        # The user's own SQL login, on this copy only (as open_sql_data_layer does).
        connection = run_config.connection
        connection.trusted_connection = credentials.windows
        connection.sql_username = credentials.username
        connection.sql_password = credentials.password
    output = Path(folder) / "feature_investigation"
    result = run_training_feature_search(
        run_config, observed, options=search_options(run_config), on_event=Progress(observed),
        output=output, csv_source=csv_source, one_vs_rest=True)
    plain = _plain({key: value for key, value in result.items() if key != "output_directory"})
    (Path(folder) / RESULT_FILE).write_text(json.dumps(plain, ensure_ascii=False, indent=1),
                                            encoding="utf-8")
    return summary(plain)
