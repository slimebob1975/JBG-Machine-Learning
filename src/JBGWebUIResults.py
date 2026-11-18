"""Results tab of the web interface (revision 295a).

The project's finished runs; for the selected run an overview (key figures,
confusion matrix with class names, most important features) and its detail
tables: the spot-check leaderboard, the mispredictions (paged) and the
feature importance. Class names and row values come from the run's own
folder and are shown to its owner only. Plain links and forms.
"""
from __future__ import annotations

from fastapi import Depends, Request
from fastapi.responses import HTMLResponse

VIEWS = (("overview", "Overview"), ("leaderboard", "Model comparison"),
         ("mispredictions", "Mispredictions"), ("feature_importance", "Feature importance"),
         ("dark_numbers", "Dark Numbers"))                                          # 298j


# 298j: the engine's Dark Number estimates (JBGDarkNumberReporting.INTERVAL_SCOPES),
# in their expected order from smallest to largest.
DARK_ESTIMATES = {"D_re_full": "Final model, all data", "D_cv_full": "Cross-trained model, all data",
                  "D_comb": "Combined", "D_cv_test": "Cross-trained model, test data"}
DARK_REASONS = {"unestimable": "cannot be estimated", "missing": "missing",
                "ambiguous": "ambiguous", "non-finite": "not a number",
                "unknown correction": "unknown correction",
                "inconsistent zero-FP result": "inconsistent",
                # 299o, JBG v1.1
                "undefined rate": "Undefined: this part has no rows of the target class or "
                                  "none of the other classes",
                "undefined correction": "Undefined: no usable correction factor (c), the "
                                        "pipeline is ill-suited to this problem"}
DARK_COLUMNS = {"Model type": "Estimate", "type": "Calculation", "target": "Target class",
                "alphas": "Alpha", "corr": "Correction (c)", "corr_model": "Correction from",
                "corr_source": "Basis of the correction", "dark_number": "Dark Number",
                "corr_train_fit": "Training fit (correction model)",           # 299q
                "corr_unseen_accuracy": "Accuracy on unseen rows",             # 299q2
                # 300e (DN-03): the out-of-fold c beside the in-sample one.
                "corr_oof": "Correction out-of-fold (c)",
                "corr_oof_low": "c out-of-fold, lower (90 %)",
                "corr_oof_high": "c out-of-fold, upper (90 %)",
                "corr_oof_quality": "Quality of c out-of-fold",
                "dark_number_oof": "Dark Number with c out-of-fold"}


# 299a2 (asked 2026-11-12): the engine's English column names in the result
# tables, shown in the interface's language. Class names, P(<class>) and
# feature names are data and stay as they are.
HEADINGS = {
    "Actual": "Actual class", "Predicted": "Predicted class", "Model": "Model",
    "Rate": "Certainty",                                         # 299c: predictions
    "Oversampling": "Oversampling", "Undersampling": "Undersampling", "Preprocessor": "Scaling",
    "Feature Reduction": "Dimensionality reduction", "Algorithm (Library)": "Algorithm (library)",
    "Components": "Components", "Mean cv": "Mean CV score", "Stdev.": "Standard deviation",
    "CV target": "CV target class", "CV target precision": "CV precision",
    "CV target recall": "CV recall", "CV target F1": "CV F1",
    "CV predicted positives": "CV predicted positives", "CV target support": "CV target class rows",
    "CV validation rows": "CV validation rows", "CV diagnostic status": "CV diagnostic status",
    "Elapsed Time": "Time (s)", "Exception": "Error",
    "Rank": "Rank", "Feature": "Feature", "Mean score decrease": "Mean score decrease",
    "Std. across repeats": "Standard deviation across repeats",
}
# The mispredictions' Model column (JBGHandler.PredictionsHandler).
MODEL_VALUES = {"cross trained": "Cross-trained model", "retrained": "Final model",
                "no model": "No model"}


def headings(columns, translate, names=None) -> list:
    """The columns' headings in the interface's language (unknown names unchanged)."""
    import re
    names = HEADINGS if names is None else names
    result = []
    for column in columns:
        repeat = re.fullmatch(r"Repeat (\d+)", str(column))
        if repeat:
            result.append(f"{translate('Repeat')} {repeat.group(1)}")
        else:
            result.append(translate(names[column]) if column in names else column)
    return result


# The engine's names for its estimate blocks ("D_cv_test - Cross-trained model").
_ESTIMATE_PREFIXES = (("D_re_full", "D_retrained_full"), ("D_cv_full", "D_cv_full"),
                      ("D_comb", "Combined"), ("D_cv_test", "D_cv_test"))
_CORRECTION_MODELS = {"Cross-trained model": "Cross-trained model", "Retrained model": "Final model"}


def matrix_counts(detail) -> dict:
    """299v: per estimate (its "Model type"), the rows registered in each class:
    the row sums of its confusion matrix (rows are the registered classes)."""
    counts, current = {}, None
    columns = detail.get("columns") or []
    for row in detail.get("rows") or []:
        if len(row) < 3:
            continue
        name = str(row[1] or "").strip()
        if name:
            current = name
            counts[current] = {}
        if current is None:
            continue
        total = 0.0
        for value in row[2:len(columns)]:
            try:
                total += float(value)
            except (TypeError, ValueError):
                pass
        counts[current][str(row[0])] = total
    return counts


def _counts_for(label: str, counts: dict):
    from JBGDarkNumberReporting import INTERVAL_SCOPES
    prefix = dict(INTERVAL_SCOPES).get(label)
    if prefix is None:
        return None
    found = [c for name, c in counts.items()
             if (name == prefix if label == "D_comb" else name.startswith(prefix))]
    return found[0] if len(found) == 1 else None


def with_growth(summary: list, counts: dict, language: str) -> list:
    """299v (asked 2026-11-16): the Dark Number as growth of the target class.
    With D the hidden share among the rows registered as another class, the
    hidden cases are D * N_rest and the target class grows by
    g = D * N_rest / N_target, where N_rest and N_target are the registered
    rows of the same estimate. The share of all real target cases that were
    missing from the register is g / (1 + g). Assumes, like D, that the rows
    registered as the target are the target."""
    def factor_text(g):
        text = f"×{1 + g:.2f}"
        return text.replace(".", ",") if language == "sv" else text
    for interval in summary:
        target = str(interval.get("target"))
        growths = []
        for point in interval.get("points", []):
            point["growth"] = None
            found = _counts_for(point.get("label", ""), counts)
            if point.get("value") is None or not found or target not in found:
                continue
            n_target = found[target]
            n_rest = sum(v for k, v in found.items() if k != target)
            if n_target <= 0:
                continue
            hidden = point["value"] * n_rest
            g = hidden / n_target
            point.update(growth=g, growth_text=f"+{percent_text(g, language)} ({factor_text(g)})",
                         hidden=hidden, registered_target=int(round(n_target)),
                         registered_rest=int(round(n_rest)),
                         missing_text=percent_text(g / (1 + g), language))
            growths.append(g)
        top = max(growths) if growths else 0.0
        for point in interval.get("points", []):
            if point.get("growth") is not None:
                point["growth_bar"] = 0.0 if top <= 0 else round(100 * point["growth"] / top, 1)
        interval["growth_range_text"] = (f"+{percent_text(min(growths), language)} – "
                                         f"+{percent_text(max(growths), language)}") if growths else ""
        interval["growth_points"] = sorted(                                   # 299w
            interval.get("points", []),
            key=lambda p: (p.get("growth") is None, p.get("growth") or 0.0))
    return summary


def percent_text(value: float, language: str) -> str:
    """A share as a percentage with two decimals ("0,10 %" in Swedish)."""
    if value > 0 and value * 100 < 0.005:
        text = "< 0.01 %"
    else:
        text = f"{value * 100:.2f} %"
    return text.replace(".", ",") if language == "sv" else text


def with_percentages(summary: list, language: str) -> list:
    """299b (asked 2026-11-12): each estimate as a percentage, with its share of
    the target's largest estimate for the bar, and the range as text."""
    for interval in summary:
        values = [p["value"] for p in interval["points"] if p.get("value") is not None]
        top = max(values) if values else 0.0
        for point in interval["points"]:
            value = point.get("value")
            point["percent"] = None if value is None else percent_text(value, language)
            point["bar"] = 0.0 if value is None or top <= 0 else round(100 * value / top, 1)
        interval["range_text"] = (f"{percent_text(min(values), language)} – "
                                  f"{percent_text(max(values), language)}") if values else ""
        # 299w (settled 2026-11-16): the four model variants form an interval
        # with subintervals, sorted from the lowest to the highest (undefined
        # last); there is no order check.
        interval["points"] = sorted(
            interval["points"],
            key=lambda p: (p.get("value") is None, p.get("value") or 0.0))
    return summary


def alpha_text(value, language: str = "sv"):
    """299f2 (asked 2026-11-13): the engine writes a list of alphas as Python
    text, e.g. "[1, np.float64(0.7205267055383298)]". Show each factor as the
    Dark Number column shows numbers (at most four significant digits, decimal
    comma in Swedish), separated by a semicolon in Swedish, where the comma is
    the decimal sign. Anything else is returned unchanged."""
    import re
    from JBGWebUI import _number_text
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not (text.startswith("[") and text.endswith("]")):
        return value
    parts = [p.strip() for p in text[1:-1].split(",")]
    numbers = []
    for part in parts:
        match = re.fullmatch(r"(?:np\.float(?:32|64)\((.+)\)|(.+))", part)
        try:
            numbers.append(float((match.group(1) or match.group(2)).strip()))
        except (AttributeError, ValueError):
            return value
    if not numbers:
        return value
    return ("; " if language == "sv" else ", ").join(
        _number_text(number, language) for number in numbers)


# 299u (asked 2026-11-16): the equation behind the run's Dark Numbers, each
# part explained (JBG v1.2). (symbol as HTML, text, calculation types it is
# shown for; None: every type.)
EQUATION_PARTS = (
    ("D", "The estimated share of hidden cases: of the rows registered as another class, "
          "the share that really belong to the target class. Capped at 100 %, where the "
          "estimate has broken down.", None),
    ("1 − TN<sub>r</sub>", "FP / (FP + TN): the share of the rows registered as another class "
                          "that the model predicts as the target class. These are the "
                          "candidates for hidden cases.", None),
    ("1 − TP<sub>r</sub>", "FN / (TP + FN): the share of the target class's own rows that the "
                          "model misses. A model that misses known cases also misses hidden "
                          "ones, so the share above is scaled up by 1 plus this share.", None),
    ("α<sub>FP</sub>", "The mean probability of the target class on the false positives: a "
                       "confident false positive counts almost fully, an uncertain one little.",
     {"separated_alpha"}),
    ("α<sub>FN</sub>", "The mean probability of not being the target class on the false "
                       "negatives. It weighs the misses only.", {"separated_alpha"}),
    ("α", "The mean certainty on all errors, the target class against the rest.",
     {"single_alpha", "non_linear_alpha"}),
    ("k", "The root of the non-linear form.", {"non_linear", "non_linear_alpha"}),
    ("c", "The correction factor 1/r from the flip test, where r is the share of "
          "deliberately relabelled rows of the target class that the model still recognises. "
          "It corrects for a model that reproduces the registered labels of rows it was "
          "trained on, so it is used for the estimates on all data and not for the unseen "
          "test part. It must lie between 1 and 10, otherwise the estimate is undefined.", None),
)


def _sampling_labels() -> dict:
    """299y: the sampling policies' labels, as on the Configuration tab."""
    from JBGConfigSchema import OPTION_LABELS
    from JBGDarkNumberSampling import POLICIES
    return {policy: OPTION_LABELS.get(policy, policy) for policy in POLICIES}


def dark_equation(calculation_type: str, translate):
    """299u: the formula card and its explained parts for one calculation type."""
    from JBGWebUIDarkNumbers import formula_cards
    card = formula_cards(translate)["formulas"].get(calculation_type)
    if card is None:
        return None
    parts = [{"symbol": symbol, "text": translate(text)} for symbol, text, types in EQUATION_PARTS
             if types is None or calculation_type in types]
    return {"type": calculation_type, "card": card, "parts": parts}


# 300e: the out-of-fold c's quality states.
OOF_QUALITY = {"reliable": "Reliable", "uncertain": "Uncertain",
               "not_estimable": "Not estimable", "not applied": "Not used (test part)"}


def _share_text(value, language: str) -> str:
    """299q: a share 0..1 as a percentage with one decimal, or "–"."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "–"
    if number != number:
        return "–"
    text = f"{100 * number:.1f} %"
    return text.replace(".", ",") if language == "sv" else text


def _is_undefined(value) -> bool:
    """299o, JBG v1.1: -1 marks an undefined Dark Number or correction factor."""
    try:
        return float(value) == -1.0
    except (TypeError, ValueError):
        return False


def readable_dark_table(detail: dict, translate, language: str = "sv") -> dict:
    """298j: the engine's Dark Number tables with readable estimate and model
    names and calculation types. Only these known columns are changed, never a
    class name. 299f2: the alphas as numbers."""
    columns = detail["columns"]
    for row in detail["rows"]:
        for index, column in enumerate(columns):
            value = row[index] if index < len(row) else ""
            if column == "Model type" and value:
                key = next((k for k, prefix in _ESTIMATE_PREFIXES if str(value).startswith(prefix)), None)
                row[index] = translate(DARK_ESTIMATES[key]) if key else value
            elif column == "corr_model" and value in _CORRECTION_MODELS:
                row[index] = translate(_CORRECTION_MODELS[value])
            elif column == "type" and isinstance(value, str):
                row[index] = value.replace("_", " ")
            elif column == "corr_oof_quality":
                row[index] = translate(OOF_QUALITY.get(str(value), str(value or "")))  # 300e
            elif column in ("corr", "dark_number", "corr_oof", "dark_number_oof") \
                    and _is_undefined(value):
                row[index] = translate("Undefined")                         # 299o
            elif column in ("corr_train_fit", "corr_unseen_accuracy"):
                row[index] = _share_text(value, language)                   # 299q
            elif column == "alphas":
                row[index] = alpha_text(value, language)
    return detail


def estimate_first(detail: dict) -> dict:
    """299e (asked 2026-11-13): in the Dark Numbers confusion matrices the
    estimate ("Model type") comes first, left of the actual class (the
    engine writes the actual class first)."""
    columns = detail["columns"]
    if len(columns) >= 2 and columns[0] == "" and columns[1] == "Model type":
        detail["columns"] = [columns[1], columns[0]] + columns[2:]
        detail["rows"] = [([row[1], row[0]] + row[2:]) if len(row) >= 2 else row
                          for row in detail["rows"]]
    return detail


# 299a: reclassification messages.
MESSAGES = {
    "corrected": ("ok", "The corrections are written to the source table."),
    "corrected_csv": ("ok", "The corrections are saved in a new version of the dataset's file."),
    "correction_failed_csv": ("error", "The dataset's file could not be updated, so nothing was changed."),
    "undone": ("ok", "The correction is undone: the old class is written back."),
    "correction_refused": ("error", "Nothing was corrected: choose a new class for at least one row."),
    "correction_failed": ("error", "The source table could not be updated, so nothing was written. "
                          "Check that your SQL sign-in may change the table."),
    "signin_needed": ("error", "Sign in to SQL Server first (Dataset tab)."),
}


# 299j: why a recommendation cannot be applied (shown on the red button).
RECOMMENDATION_REASONS = {
    "dataset_gone": "The investigated dataset no longer exists.",
    "no_roles": "The investigated dataset has no column roles.",
    "roles_changed": "The dataset's column roles have changed since the investigation, "
                     "so the columns no longer match.",
    "keeps_all": "The recommendation keeps every variable, so there is nothing to change.",
    "unreadable": "The investigation's result cannot be read.",
}


def add_results_tab(app, *, principal_dependency, render, active_project, runs, results,
                    reclassification=None, redirect=None, recommendation=None) -> None:
    from fastapi import Form
    from JBGApplicationContracts import RunReference
    from JBGRunResults import RunResultsUnavailable
    from JBGWebUI import request_language, translator

    @app.get("/ui/results", response_class=HTMLResponse, include_in_schema=False)
    def results_tab(request: Request, run: str = "", view: str = "overview", page: int = 1,
                    principal=Depends(principal_dependency)):
        return render(request, principal, "results.html", "results",
                      **context_for(request, principal, run, view, page))

    def context_for(request, principal, run, view, page):
        owner = principal.principal_key
        project = active_project(request, owner)
        view = view if view in dict(VIEWS) else "overview"
        context = {"no_project": project is None, "finished": [], "selected_run": None,
                   "views": VIEWS, "view": view, "overview": None, "labels": [],
                   "detail": None, "detail_missing": False, "available": {},
                   "has_folder": False, "dark_summary": [], "dark_matrix": None,
                   "correctable": False, "corrected": {}, "correction_log": [], "review": None,
                   "correction_source": "",
                   "dark_estimates": DARK_ESTIMATES, "dark_reasons": DARK_REASONS,
                   "sampling_labels": _sampling_labels(),                       # 299y
                   "dark_equation": None, "dark_view": "share", "dark_record": None,
                   "dark_sampling_risks": [],
                   "dark_columns": DARK_COLUMNS, "investigation": None, "apply": None}
        if project is not None:
            # 296a: results belong to training runs; prediction runs are on the
            # Prediction tab.
            context["finished"] = [r for r in runs.list_project_runs(owner, project["project_id"])
                                   if r["status"] == "succeeded"
                                   and r.get("kind", "training") in ("training", "investigation")]
            chosen = run or (context["finished"][0]["run_id"] if context["finished"] else "")
            item = next((r for r in context["finished"] if r["run_id"] == chosen), None)
            if item is not None and item.get("kind") == "investigation":
                # 299j: a feature investigation has one view: its recommendation.
                context["selected_run"] = chosen
                context["is_investigation"] = True
                context["overview"] = runs.overview(owner, RunReference(chosen))
                found = recommendation(owner, project["project_id"], chosen) \
                    if recommendation is not None else None
                if found is not None:
                    view_, plan, dataset_id = found
                    context["investigation"] = view_ or None
                    context["apply"] = {
                        "dataset_id": dataset_id, "mismatch": plan.get("mismatch", []),
                        "ignore": plan.get("ignore", []), "reason": plan.get("reason"),
                        "reason_text": RECOMMENDATION_REASONS.get(plan.get("reason"), "")}
                context["tab_messages"] = MESSAGES
                return context
            if item is not None:
                context["selected_run"] = chosen
                context["overview"] = runs.overview(owner, RunReference(chosen))
                try:
                    context["has_folder"] = results.has_folder(owner, chosen)
                    context["labels"] = results.class_labels(owner, chosen)
                    context["available"] = results.available(owner, chosen)
                    if view != "overview":
                        context["detail"] = results.detail(owner, chosen, view, page=page)
                        translate = translator(request_language(request))
                        detail = context["detail"]
                        detail["headings"] = headings(
                            detail["columns"], translate,
                            DARK_COLUMNS if view == "dark_numbers" else None)
                        if view == "mispredictions" and "Model" in detail["columns"]:
                            at = detail["columns"].index("Model")
                            for row in detail["rows"]:
                                if at < len(row) and row[at] in MODEL_VALUES:
                                    row[at] = translate(MODEL_VALUES[row[at]])
                    if view == "mispredictions" and reclassification is not None \
                            and reclassification.correctable(owner, chosen):
                        # 299a: SQL runs: pick the right class, review, confirm.
                        context["correctable"] = True
                        context["correction_source"] = reclassification.source(owner, chosen)
                        context["corrected"] = reclassification.current(owner, chosen)
                        context["correction_log"] = list(enumerate(reclassification.log(owner, chosen)))
                    if view == "dark_numbers":
                        # 298j: the estimates per target, then the calculation
                        # table (above) and the confusion matrices.
                        translate = translator(request_language(request))
                        readable_dark_table(context["detail"], translate,
                                            request_language(request))
                        context["dark_summary"] = with_percentages(
                            results.dark_number_summary(owner, chosen), request_language(request))
                        # 299v: the hidden share, or the target class's growth.
                        context["dark_view"] = ("growth" if request.query_params.get("dark_view")
                                                == "growth" else "share")
                        try:
                            counts = matrix_counts(results.detail(
                                owner, chosen, "dark_numbers_matrix", page_size=500))
                        except RunResultsUnavailable:
                            counts = {}
                        with_growth(context["dark_summary"], counts, request_language(request))
                        types = [i.get("formula") for i in context["dark_summary"] if i.get("formula")]
                        # 299x: the equation only for runs with a result record
                        # (computed with this version); older runs get a note.
                        record = results.dark_number_record(owner, chosen)
                        context["dark_record"] = record
                        # 299y (DN-02): targets whose correction test kept the
                        # pipeline's SMOTE with the target in the majority.
                        context["dark_sampling_risks"] = sorted({
                            str(e.get("target")) for e in (record or {}).get("estimates", [])
                            if (e.get("sampling") or {}).get("contamination_risk")})
                        if types and record is not None:
                            context["dark_equation"] = dark_equation(types[0], translate)  # 299u
                        try:
                            context["dark_matrix"] = estimate_first(readable_dark_table(
                                results.detail(owner, chosen, "dark_numbers_matrix",
                                               page_size=500), translate,
                                request_language(request)))
                        except RunResultsUnavailable:
                            context["dark_matrix"] = None
                except RunResultsUnavailable:
                    context["detail_missing"] = view != "overview"
        context["tab_messages"] = MESSAGES
        return context

    if reclassification is None or redirect is None:
        return
    from JBGReclassification import CorrectionFailed, CorrectionRefused

    def is_csv(principal, run_id) -> bool:
        try:
            return reclassification.source(principal.principal_key, run_id) == "csv"
        except CorrectionRefused:
            return False

    def failed_message(principal, run_id) -> str:
        return "correction_failed_csv" if is_csv(principal, run_id) else "correction_failed"

    def chosen_classes(form) -> dict:
        return {key[len("corr:"):]: value for key, value in form.multi_items()
                if key.startswith("corr:") and value}

    @app.post("/ui/results/{run_id}/corrections/review", response_class=HTMLResponse,
              include_in_schema=False)
    async def review_corrections(request: Request, run_id: str, page: int = 1,
                                 principal=Depends(principal_dependency)):
        """299a: the corrections to confirm; nothing is written yet."""
        form = await request.form()
        try:
            changes = reclassification.review(principal.principal_key, run_id, chosen_classes(form))
        except CorrectionRefused:
            return redirect("/ui/results", run=run_id, view="mispredictions",
                            message="correction_refused")
        context = context_for(request, principal, run_id, "mispredictions", page)
        context["review"] = changes
        context["correction_source"] = reclassification.source(principal.principal_key, run_id)
        return render(request, principal, "results.html", "results", **context)

    @app.post("/ui/results/{run_id}/corrections", include_in_schema=False)
    async def apply_corrections(request: Request, run_id: str,
                                principal=Depends(principal_dependency)):
        form = await request.form()
        try:
            reclassification.apply(principal, run_id, chosen_classes(form))
        except CorrectionRefused:
            return redirect("/ui/results", run=run_id, view="mispredictions",
                            message="correction_refused")
        except PermissionError:
            return redirect("/ui/results", run=run_id, view="mispredictions",
                            message="signin_needed")
        except CorrectionFailed:
            return redirect("/ui/results", run=run_id, view="mispredictions",
                            message=failed_message(principal, run_id))
        return redirect("/ui/results", run=run_id, view="mispredictions",
                        message="corrected_csv" if is_csv(principal, run_id) else "corrected")

    @app.post("/ui/results/{run_id}/corrections/{index}/undo", include_in_schema=False)
    def undo_correction(run_id: str, index: int, principal=Depends(principal_dependency)):
        try:
            reclassification.undo(principal, run_id, index)
        except CorrectionRefused:
            return redirect("/ui/results", run=run_id, view="mispredictions",
                            message="correction_refused")
        except PermissionError:
            return redirect("/ui/results", run=run_id, view="mispredictions",
                            message="signin_needed")
        except CorrectionFailed:
            return redirect("/ui/results", run=run_id, view="mispredictions",
                            message=failed_message(principal, run_id))
        return redirect("/ui/results", run=run_id, view="mispredictions", message="undone")
