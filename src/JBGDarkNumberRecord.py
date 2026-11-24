"""The Dark Numbers result record of a run (revision 299x).

Agreed 2026-11-16 (DN-01, the result format): next to the engine's CSV files
(kept unchanged for Voila and older readers), every Dark Numbers computation
writes one JSON record with a schema version, the method and its version, the
parameters used, and one entry per estimate. v1.2 writes the estimand D_JBG
with no interval; v2 and the new methods add their estimates (H, U, N_hidden,
with intervals and quality states) to the same list, so a run can show them
side by side. A run without the record was computed with an earlier version.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

SCHEMA_VERSION = 1
RECORD_SUFFIX = ".json"

# The estimate's model variant from the calculation table's "Model type".
_SCOPES = (("D_retrained_full", "D_re_full"), ("D_cv_full", "D_cv_full"),
           ("Combined (legacy full-data)", "D_comb"), ("D_cv_test", "D_cv_test"))


def _scope(model_type: str):
    for prefix, scope in _SCOPES:
        if model_type == prefix or model_type.startswith(prefix + " - ") or \
                (scope != "D_comb" and model_type.startswith(prefix)):
            return scope
    return None


def _number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def parameters(config, used: dict) -> dict:
    """The settings the computation used (``used``: what the handler passed)."""
    from JBGDarkNumbers import DarkNumberCalculator as Calc
    mode = config.mode
    return {
        "calculation_type": config.get_dark_number_calculation_type(),
        "method": getattr(mode.dark_number_method, "name", str(mode.dark_number_method)),
        "alpha": getattr(mode.dark_number_alpha, "name", str(mode.dark_number_alpha)),
        "target_class": config.get_dark_number_target() or None,
        "flip_fraction": _number(used.get("flip_fraction")
                                 if used.get("flip_fraction") is not None
                                 else mode.dark_number_flip_fraction),
        "flip_test_folds": Calc.FLIP_TEST_FOLDS,
        "flip_test_repeats": int(getattr(mode, "dark_number_flip_repeats",
                                         Calc.FLIP_TEST_REPEATS)),              # 300n
        "correction_min": Calc.CORRECTION_MIN,
        "correction_max": float(getattr(mode, "dark_number_c_max", Calc.CORRECTION_MAX)),
        "c_warning": float(getattr(mode, "dark_number_c_warning", 10.0)),
        "cap": Calc.CAP,
        "memorisation_fit": Calc.MEMORISATION_FIT, "memorisation_gap": Calc.MEMORISATION_GAP,
        "memorisation_threshold": Calc.MEMORISATION_THRESHOLD,
        "root_degree": used.get("root_degree", 3),
        "random_state": used.get("random_state"),
        # 299y (DN-02): sampling in the flip test behind c.
        "sampling_policy": getattr(mode, "dark_number_sampling_policy", "PIPELINE"),
        # 300l, JBG 1.3: c = c_in / c_unseen from the flip test's folds.
        "correction": "overtraining factor (c_in / c_unseen)",
        "reliable_halfwidth": 0.25,
    }


def estimates(frame, sampling: dict = None) -> list:
    """One entry per row of the calculation table (v1.2: estimand D_JBG)."""
    entries, model_type = [], ""
    for _, row in frame.iterrows():
        name = str(row.get("Model type") or "").strip()
        if name:
            model_type = name
        value = _number(row.get("dark_number"))
        capped = str(row.get("capped", "")).strip().lower() in ("true", "1")
        if value == -1.0:
            status, reason = "undefined", ("undefined correction"
                                           if str(row.get("corr_source", "")).startswith("undefined/")
                                           else "undefined rate")
            value = None
        elif value is None:
            status, reason = "undefined", "non-finite"
        else:
            status, reason = ("capped", "") if capped else ("ok", "")
        entries.append({
            "method": "JBG", "scope": _scope(model_type), "model": model_type,
            "target": str(row.get("target")), "estimand": "D_JBG",
            "calculation_type": str(row.get("type")), "value": value, "interval": None,
            "status": status, "reason": reason,
            "corr": _number(row.get("corr")), "corr_source": str(row.get("corr_source", "")),
            # 300l, JBG 1.3: what c is made of, its interval and quality.
            "corr_in_sample": _number(row.get("corr_in_sample")),
            "corr_unseen": _number(row.get("corr_unseen")),
            "corr_interval": [_number(row.get("corr_low")), _number(row.get("corr_high"))]
            if row.get("corr_low") is not None else None,
            "corr_quality": (str(row.get("corr_quality"))
                             if row.get("corr_quality") is not None else None),
            # 299y: the flip test's sampling for this correction model and target.
            "sampling": (sampling or {}).get((str(row.get("corr_model", "")), str(row.get("target")))),
        })
    return entries


def build(config, frame, used: dict) -> dict:
    from JBGDarkNumbers import DarkNumberCalculator
    return {"schema_version": SCHEMA_VERSION,
            "method": {"name": "JBG", "version": DarkNumberCalculator.METHOD_VERSION},
            "parameters": parameters(config, used),
            "estimates": estimates(frame, {(str(m), str(t)): v for (m, t), v in
                                           (used.get("sampling") or {}).items()})}


def record_path(csv_path) -> Path:
    path = Path(csv_path)
    return path.with_suffix(RECORD_SUFFIX)


def write(config, frame, used: dict, csv_path) -> Path:
    path = record_path(csv_path)
    path.write_text(json.dumps(build(config, frame, used), ensure_ascii=False, indent=1),
                    encoding="utf-8")
    return path


def read(folder: Path):
    """The record in a run's ``output/csvs`` folder, or None (an earlier version)."""
    if not folder.is_dir():
        return None
    found = sorted((p for p in folder.glob("dark_numbers_*" + RECORD_SUFFIX)
                    if not p.name.startswith("dark_numbers_conf_matrix_")),
                   key=lambda p: (len(p.name), p.name))
    if not found:
        return None
    try:
        record = json.loads(found[0].read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return record if isinstance(record, dict) and record.get("schema_version") else None
