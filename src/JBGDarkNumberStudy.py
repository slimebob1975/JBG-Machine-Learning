"""Validation study of the Dark Number method JBG 1.2 against a known truth
(revision 299z, agreed 2026-11-16).

Outside the normal training and prediction flow. Synthetic populations with a
chosen true hidden share H (of the rows registered as another class, the share
that really are the target class) are generated; models are trained on the
registered labels, as in a real run; the engine's own Dark Number computation
(PredictionsHandler.get_dark_numbers, the default settings of JBG 1.2) is run;
and each of the four estimates is compared with the true H in its own part of
the data (the test part, or all data). The protocol, the thresholds and the
decision rules are in docs/dark_numbers/DN-06_v12_validation_protocol.md.

Usage (from src/):  python -m JBGDarkNumberStudy --repeats 10 --out ../study
"""
from __future__ import annotations

import argparse
import json
import math
import time
import warnings
from dataclasses import asdict, dataclass
from itertools import product
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

TARGET, REST = "T", "R"
SEPARATIONS = {"weak": 0.5, "medium": 1.0, "strong": 2.0}
SCOPES = {"D_cv_test": "test", "D_cv_full": "all", "D_retrained_full": "all",
          "Combined (legacy full-data)": "all"}


@dataclass(frozen=True)
class Cell:
    hidden_share: float          # true H among the rows registered as REST
    target_share: float          # true share of TARGET in the population
    separation: str              # weak, medium, strong
    mechanism: str = "one_sided"  # one_sided, two_sided, feature_dependent
    model: str = "logistic"      # logistic, mlp
    rows: int = 4000

    @property
    def assumptions_hold(self) -> bool:
        return self.mechanism == "one_sided"


# 299z2: at most this share of the true target rows may be hidden. The hidden
# share H among the rows registered as the rest cannot exceed about the target
# share (all target rows hidden), so H = 20 % with a 15 % target share is
# impossible, and H = 10 % would hide 63 % of the target rows.
MAX_HIDDEN_TARGET_SHARE = 0.5


def hidden_fraction_of_targets(cell: "Cell") -> float:
    """The share of the true target rows that must be hidden for the cell's H."""
    if cell.hidden_share <= 0:
        return 0.0
    hidden = cell.hidden_share * (1 - cell.target_share) / (1 - cell.hidden_share)
    return hidden / cell.target_share


def feasible(cell: "Cell") -> bool:
    return hidden_fraction_of_targets(cell) <= MAX_HIDDEN_TARGET_SHARE


def all_main_cells(models=("logistic", "mlp")) -> list:
    return [Cell(h, q, s, "one_sided", m) for h, q, s, m in product(
        (0.0, 0.02, 0.05, 0.10, 0.20), (0.15, 0.50, 0.85), ("weak", "strong"), models)]


def main_cells(models=("logistic", "mlp")) -> list:
    """The main matrix: assumptions hold (one-sided hiding), feasible cells."""
    return [cell for cell in all_main_cells(models) if feasible(cell)]


def excluded_cells(models=("logistic", "mlp")) -> list:
    """Cells left out because they are impossible by construction (299z2)."""
    return [cell for cell in all_main_cells(models) if not feasible(cell)]


def broken_cells(models=("logistic", "mlp")) -> list:
    """Assumptions broken: cases also hidden the other way, or by feature."""
    return [Cell(h, 0.50, "medium", mech, m) for h, mech, m in product(
        (0.05, 0.10), ("two_sided", "feature_dependent"), models)]


def population(cell: Cell, seed: int):
    """(X, registered labels, true labels) with exactly the cell's true H."""
    rng = np.random.default_rng(seed)
    n = cell.rows
    true = np.where(rng.random(n) < cell.target_share, TARGET, REST)
    shift = SEPARATIONS[cell.separation] * np.array([1.0, 0.6, 0.3, 0.0, 0.0, 0.0])
    X = rng.normal(size=(n, 6)) + np.outer(true == TARGET, shift)
    registered = true.copy()
    targets = np.flatnonzero(true == TARGET)
    rests = np.flatnonzero(true == REST)
    hidden = int(round(cell.hidden_share * len(rests) / (1 - cell.hidden_share))) \
        if cell.hidden_share < 1 else 0
    if hidden > MAX_HIDDEN_TARGET_SHARE * len(targets):
        raise ValueError("infeasible cell: too many target rows would have to be hidden")
    if hidden > 0:
        if cell.mechanism == "feature_dependent":
            # Missing at random, not completely: weaker cases are hidden more often.
            weight = np.exp(-1.5 * X[targets, 0])
            chosen = rng.choice(targets, size=hidden, replace=False, p=weight / weight.sum())
        else:
            chosen = rng.choice(targets, size=hidden, replace=False)
        registered[chosen] = REST
    if cell.mechanism == "two_sided" and hidden > 0:
        # As many true REST rows registered as TARGET (false registrations).
        registered[rng.choice(rests, size=min(hidden, len(rests) - 2), replace=False)] = TARGET
    return pd.DataFrame(X), pd.Series(registered), pd.Series(true)


def true_hidden_share(registered: pd.Series, true: pd.Series) -> float:
    rest = registered == REST
    return float((true[rest] == TARGET).mean()) if rest.any() else float("nan")


def _model(kind: str, seed: int):
    from sklearn.linear_model import LogisticRegression
    from sklearn.neural_network import MLPClassifier
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    algorithm = LogisticRegression(max_iter=1000) if kind == "logistic" else \
        MLPClassifier(hidden_layer_sizes=(32,), max_iter=500, random_state=seed)
    return Pipeline([("STA", StandardScaler()), ("ALG", algorithm)])


class _Log:
    def __init__(self):
        self.warnings = []

    def print_warning(self, message):
        self.warnings.append(str(message))

    def print_info(self, *_args, **_kwargs):
        return None


def _handler(log):
    from JBGHandler import PredictionsHandler
    ph = object.__new__(PredictionsHandler)
    jobs = SimpleNamespace(execute_n_job=lambda operation, estimator, X, y, **kw:
                           operation(estimator, X, y))
    ph.handler = SimpleNamespace(
        logger=log, STANDARD_DESIRED_N_JOBS=1, get_handler=lambda name: jobs,
        config=SimpleNamespace(
            get_dark_number_flip_fraction=lambda: 0.2,
            should_use_experimental_perturbed_dark_number_fallback=lambda: False,
            mode=SimpleNamespace(dark_number_sampling_policy="PIPELINE")))
    return ph


def _hits(model, X, registered, true):
    """(flagged rows, the share of them truly the target) for one model."""
    predicted = pd.Series(model.predict(X.to_numpy()), index=registered.index)
    flagged = (registered == REST) & (predicted == TARGET)
    count = int(flagged.sum())
    return count, (float((true[flagged] == TARGET).mean()) if count else math.nan)


def run_once(cell: Cell, seed: int) -> list:
    """One population: the four estimates against the truth in their scope."""
    X, registered, true = population(cell, seed)
    n = len(X)
    order = np.random.default_rng(seed + 1).permutation(n)
    test = order[: n // 5]
    train = order[n // 5:]
    cross = _model(cell.model, seed).fit(X.iloc[train].to_numpy(), registered.iloc[train])
    final = _model(cell.model, seed).fit(X.to_numpy(), registered)
    log = _Log()
    ph = _handler(log)
    started = time.perf_counter()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ph.get_dark_numbers(
            X=X, Y=registered, models=[cross, final], model_names=["Cross", "Final"],
            target_class=TARGET, type="separated_alpha", random_state=seed,
            X_validation=X.iloc[test], Y_validation=registered.iloc[test],
            X_cv_training=X.iloc[train], Y_cv_training=registered.iloc[train])
    seconds = time.perf_counter() - started
    frame = ph.dark_numbers.copy()
    frame["Model type"] = frame["Model type"].replace("", pd.NA).ffill().astype(str)
    truth = {"test": true_hidden_share(registered.iloc[test], true.iloc[test]),
             "all": true_hidden_share(registered, true)}
    # 300d (asked 2026-11-18): the hit rate. Of the rows the model flags
    # (registered as the rest, predicted as the target), the share that are
    # truly hidden cases; random selection would hit the true hidden share.
    flags = {"test": _hits(cross, X.iloc[test], registered.iloc[test], true.iloc[test]),
             "cross_all": _hits(cross, X, registered, true),
             "final_all": _hits(final, X, registered, true)}
    flag_source = {"D_cv_test": "test", "D_cv_full": "cross_all",
                   "D_retrained_full": "final_all", "Combined (legacy full-data)": "final_all"}
    memorises = any("memorise" in w for w in log.warnings)
    rows = []
    for _, row in frame[frame["target"].astype(str) == TARGET].iterrows():
        name = row["Model type"]
        scope = next((s for prefix, s in SCOPES.items() if name.startswith(prefix)), None)
        if scope is None:
            continue
        value = float(row["dark_number"])
        oof = float(row["dark_number_oof"]) if "dark_number_oof" in row \
            and row["dark_number_oof"] == row["dark_number_oof"] else value
        estimate = next(p for p in SCOPES if name.startswith(p))
        flagged, hit_rate = flags[flag_source[estimate]]
        rows.append({**asdict(cell), "seed": seed, "estimate": estimate,
                     "flagged": flagged, "hit_rate": hit_rate,
                     "lift": hit_rate / truth[scope] if truth[scope] and hit_rate == hit_rate
                     else math.nan,
                     "true_H": truth[scope],
                     # 300e: the Dark Number with the out-of-fold c, and that c.
                     "D_oof": None if oof == -1.0 else oof,
                     "c_oof": float(row["corr_oof"]) if "corr_oof" in row else math.nan,
                     "c_oof_quality": str(row.get("corr_oof_quality", "")),
                     "D": None if value == -1.0 else value, "undefined": value == -1.0,
                     "capped": bool(row.get("capped", False)), "c": float(row["corr"]),
                     "memorisation_warning": memorises, "seconds": seconds})
    return rows


# --- Pre-registered thresholds (docs/dark_numbers/DN-06_v12_validation_protocol.md) --------

THRESHOLDS = {
    "zero_mean_pp": 1.0,          # H = 0: mean estimate at most 1 percentage point
    "zero_alarm_pp": 2.0,         # ... and above 2 points in at most 10 % of repeats
    "zero_alarm_share": 0.10,
    "bias_pp": 2.0, "bias_rel": 0.25,
    "mae_pp": 3.0, "mae_rel": 0.35,
    "undefined_share": 0.20,      # medium and strong separation
    "stability_rel": 0.5,         # std over seeds at most half the truth (H >= 5 %)
}


def _measures(group, column: str) -> dict:
    """Bias, MAE, RMSE, spread and the verdict for one estimate column."""
    t = THRESHOLDS
    undefined = group[column].isna()
    defined = group[~undefined]
    error_pp = 100 * (defined[column] - defined["true_H"])
    truth_pp = 100 * group["true_H"].mean()
    m = dict(undefined_share=float(undefined.mean()),
             mean_pp=float(100 * defined[column].mean()) if len(defined) else math.nan,
             bias_pp=float(error_pp.mean()) if len(defined) else math.nan,
             mae_pp=float(error_pp.abs().mean()) if len(defined) else math.nan,
             rmse_pp=float(np.sqrt((error_pp ** 2).mean())) if len(defined) else math.nan,
             std_pp=float(100 * defined[column].std(ddof=1)) if len(defined) > 1 else math.nan)
    first = group.iloc[0]
    if first["mechanism"] != "one_sided":
        verdict = "assumptions broken (reported only)"
    elif first["hidden_share"] == 0:
        alarm = float((100 * defined[column] > t["zero_alarm_pp"]).mean()) if len(defined) else 0.0
        verdict = "pass" if m["mean_pp"] <= t["zero_mean_pp"] and \
            alarm <= t["zero_alarm_share"] else "fail"
    else:
        bias_ok = abs(m["bias_pp"]) <= max(t["bias_pp"], t["bias_rel"] * truth_pp)
        mae_ok = m["mae_pp"] <= max(t["mae_pp"], t["mae_rel"] * truth_pp)
        stable = truth_pp < 5 or m["std_pp"] <= t["stability_rel"] * truth_pp
        verdict = "pass" if (bias_ok and mae_ok and stable) else "fail"
    if first["mechanism"] == "one_sided" and first["separation"] != "weak" \
            and m["undefined_share"] > t["undefined_share"]:
        verdict = "fail"
    m["verdict"] = verdict
    return m


def summarise(results: pd.DataFrame) -> pd.DataFrame:
    """Per cell and estimate: the measures and the verdicts (300e: also for the
    Dark Number with the out-of-fold c, suffix _oof)."""
    keys = ["hidden_share", "target_share", "separation", "mechanism", "model", "estimate"]
    out = []
    for key, group in results.groupby(keys, dropna=False):
        row = dict(zip(keys, key))
        row.update(repeats=len(group), truth_pp=100 * group["true_H"].mean(),
                   capped_share=float(group["capped"].mean()))
        row.update(_measures(group, "D"))
        if "D_oof" in group:
            row.update({f"{name}_oof": value for name, value in _measures(group, "D_oof").items()})
        row.update(warning_share=float(group["memorisation_warning"].mean()),
                   # 300d: reported only, no threshold (the protocol is unchanged).
                   hit_rate_pp=float(100 * group["hit_rate"].mean())
                   if "hit_rate" in group and group["hit_rate"].notna().any() else math.nan,
                   lift=float(group["lift"].mean())
                   if "lift" in group and group["lift"].notna().any() else math.nan,
                   seconds=float(group["seconds"].mean()))
        out.append(row)
    return pd.DataFrame(out)


def run_study(cells, repeats: int, out: Path, first_seed: int = 1000) -> pd.DataFrame:
    out.mkdir(parents=True, exist_ok=True)
    rows, errors = [], []
    for index, cell in enumerate(cells):
        for r in range(repeats):
            seed = first_seed + 97 * index + r
            try:
                rows.extend(run_once(cell, seed))
            except Exception as error:                 # 299z2: recorded, the study goes on
                errors.append({**asdict(cell), "seed": seed,
                               "error": f"{type(error).__name__}: {error}"})
        pd.DataFrame(rows).to_csv(out / "results.csv", index=False)       # progress kept
        pd.DataFrame(errors).to_csv(out / "errors.csv", index=False)
    results = pd.DataFrame(rows)
    summary = summarise(results)
    summary.to_csv(out / "summary.csv", index=False)
    (out / "thresholds.json").write_text(json.dumps(THRESHOLDS, indent=1), encoding="utf-8")
    return summary


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Validate JBG 1.2 against a known truth.")
    parser.add_argument("--repeats", type=int, default=10)
    parser.add_argument("--out", type=Path, default=Path("dark_number_study"))
    parser.add_argument("--models", default="logistic,mlp")
    parser.add_argument("--broken", action="store_true", help="also the broken-assumption cells")
    args = parser.parse_args(argv)
    models = tuple(args.models.split(","))
    cells = main_cells(models) + (broken_cells(models) if args.broken else [])
    args.out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{**asdict(c), "hidden_fraction_of_targets": hidden_fraction_of_targets(c)}
                  for c in excluded_cells(models)]).to_csv(args.out / "excluded_cells.csv",
                                                           index=False)
    summary = run_study(cells, args.repeats, args.out)
    print(summary.groupby(["estimate", "verdict"]).size())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
