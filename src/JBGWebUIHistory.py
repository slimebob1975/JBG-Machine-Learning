"""301c: the Run History tab (Körhistorik), tab 8 of the design.

Kept (decided 2026-11-24) for what the Training and Results tabs do not have:

- every run of the project in one list (training runs, prediction runs and
  feature investigations), with filters on kind, status, dataset and
  configuration;
- the settings a run used against the configuration's current version, and
  its column roles against the dataset's current roles;
- two runs compared side by side: their results, then every setting where
  they differ;
- rerun (agreed 2026-11-24): training runs and feature investigations start
  again with the same configuration version and dataset.

The settings come from the stored configuration version a run used (versions
are never changed), the column roles from the configuration the run itself
recorded. Runs are listed for their owner only, as on the other tabs.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import Depends, Request
from fastapi.responses import HTMLResponse

from JBGApplicationContracts import RunReference
from JBGWebUIRun import MESSAGES as JBGWebUIRun_MESSAGES

KINDS = (("training", "Training run"), ("prediction", "Prediction run"),
         ("investigation", "Feature investigation"))
STATUSES = (("succeeded", "Succeeded"), ("failed", "Failed"), ("cancelled", "Cancelled"),
            ("interrupted", "Interrupted"), ("running", "Running"), ("queued", "Queued"))
RERUNNABLE = ("training", "investigation")

# The column roles, as a run recorded them and as the dataset holds them now.
ROLES = (("id_column", "ID column"), ("class_column", "Class column"),
         ("numeric", "Numeric variables"), ("text", "Text variables"),
         ("categorical", "Categorical variables"), ("date", "Date variables"),
         ("group_column", "Group column"), ("categorical_limit", "Limit for categorisation"))
# Settings that the column roles set (compared as roles, not as settings).
ROLE_KEYS = {"mode.date_columns", "mode.category_text_columns", "mode.categorical_limit",
             "mode.validation_group_column", "mode.excluded_predictor_columns"}

MESSAGES = {
    "refused": ("error", "The run could not be started again."),
    "run_in_progress": ("error", "A run is queued or running in the project. Wait until it has finished."),
    "not_fitting": ("error", "The column roles do not fit the dataset."),
    "signin_needed": ("error", "Sign in to SQL Server first."),
    # The Run tab's own texts (already translated).
    "groups_not_supported": JBGWebUIRun_MESSAGES["groups_not_supported"],
    "id_not_integer": JBGWebUIRun_MESSAGES["id_not_integer"],
    "not_rerunnable": ("error", "Only training runs and feature investigations can be run again."),
    "unavailable": ("error", "The run is no longer available."),
}


def roles_from_snapshot(configuration: dict) -> dict:
    """The column roles a run used, from the configuration it recorded."""
    connection = configuration.get("connection") or {}
    mode = configuration.get("mode") or {}
    categorical = list(mode.get("category_text_columns") or [])
    dates = [name for name in str(mode.get("date_columns") or "").split(",") if name]
    group = mode.get("validation_group_column") or ""
    text = [name for name in connection.get("data_text_columns") or []
            if name not in categorical and name not in dates and name != group]
    return {"id_column": connection.get("id_column") or "",
            "class_column": connection.get("class_column") or "",
            "numeric": list(connection.get("data_numerical_columns") or []), "text": text,
            "categorical": categorical, "date": dates, "group_column": group,
            "categorical_limit": mode.get("categorical_limit")}


def roles_from_dataset(roles) -> dict:
    """The column roles the dataset holds now."""
    return {"id_column": roles.id_column or "", "class_column": roles.class_column or "",
            "numeric": roles.by_role("numeric"), "text": roles.by_role("text"),
            "categorical": roles.by_role("categorical"), "date": roles.by_role("date"),
            "group_column": roles.group_column or "", "categorical_limit": roles.categorical_limit}


def _same(left, right) -> bool:
    if isinstance(left, list) or isinstance(right, list):
        return sorted(map(str, left or [])) == sorted(map(str, right or []))
    if left in (None, "") and right in (None, ""):
        return True
    return left == right


def value_text(value, translate, language: str, options: dict | None = None) -> str:
    """A setting's value as the form shows it."""
    if value is None or value == "" or value == []:
        return "–"
    if isinstance(value, bool):
        return translate("Yes") if value else translate("No")
    options = options or {}
    if isinstance(value, list):
        return ", ".join(translate("All") if item == "ALL" else options.get(item, str(item))
                         for item in value)
    if isinstance(value, dict):
        return ", ".join(f"{key}: {value_text(item, translate, language)}"
                         for key, item in sorted(value.items())) or "–"
    if value in options:
        return options[value]
    if isinstance(value, float):
        text = f"{value:g}"
        return text.replace(".", ",") if language == "sv" else text
    return str(value)


def setting_differences(schema: dict, left: dict, right: dict, translate, language: str) -> list:
    """Rows (label, left, right) for each form setting where two stored
    settings differ, in the form's order."""
    rows = []
    for field in schema["fields"]:
        key = field["key"]
        if key in ROLE_KEYS:
            continue
        section, name = key.split(".", 1)
        if field["kind"] == "parameters":
            name = "model_parameters"
        a = (left.get(section) or {}).get(name)
        b = (right.get(section) or {}).get(name)
        if _same(a, b):
            continue
        options = {option["value"]: option["label"] for option in field.get("options") or []}
        label = field["label"] if field["kind"] != "parameters" else translate("Algorithm settings")
        rows.append((label, value_text(a, translate, language, options),
                     value_text(b, translate, language, options)))
    return rows


def role_differences(left: dict, right: dict, translate, language: str) -> list:
    return [(translate(label), value_text(left.get(key), translate, language),
             value_text(right.get(key), translate, language))
            for key, label in ROLES if not _same(left.get(key), right.get(key))]


def interval_text(interval: dict, language: str) -> str:
    values = [p["value"] for p in interval.get("points") or [] if p.get("value") is not None]
    if not values:
        return "–"

    def percent(value):
        text = f"{value * 100:.2f} %"
        return text.replace(".", ",") if language == "sv" else text
    low, high = min(values), max(values)
    return percent(low) if low == high else f"{percent(low)} – {percent(high)}"


def duration_text(item: dict, language: str) -> str:
    if not item.get("finished_at"):
        return "–"
    try:
        seconds = (datetime.fromisoformat(item["finished_at"])
                   - datetime.fromisoformat(item["created_at"])).total_seconds()
    except (TypeError, ValueError):
        return "–"
    minutes, seconds = divmod(int(round(max(seconds, 0))), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours} h {minutes} min" if hours else f"{minutes} min {seconds} s"


def winning_pipeline(detail: dict) -> str:
    """The cross-validation leaderboard's best row without an exception."""
    columns = detail.get("columns") or []
    if "Mean cv" not in columns:
        return ""
    score = columns.index("Mean cv")
    error = columns.index("Exception") if "Exception" in columns else None
    parts = [columns.index(name) for name in ("Oversampling", "Undersampling", "Preprocessor",
                                              "Feature Reduction") if name in columns]
    algorithm = next((columns.index(name) for name in ("Algorithm (Library)", "Algorithm")
                      if name in columns), None)
    best = None
    for row in detail.get("rows") or []:
        value = row[score] if score < len(row) else None
        if not isinstance(value, (int, float)) or (error is not None and error < len(row)
                                                   and str(row[error]).strip()):
            continue
        if best is None or value > best[score]:
            best = row
    if best is None:
        return ""
    names = [str(best[i]) for i in parts if i < len(best) and str(best[i]) not in
             ("", "NOG", "NUG", "NOS", "NOR")]
    if algorithm is not None and algorithm < len(best):
        names.append(str(best[algorithm]))
    return " · ".join(names)


def add_history_tab(app, *, principal_dependency, render, redirect, active_project, runs,
                    results, datasets, configurations, project_runs, inspection) -> None:
    from JBGConfigSchema import configuration_schema
    from JBGConfigurationService import _server_template
    from JBGProjectRuns import (IdColumnNotInteger, InvestigationRefused, RunDoesNotMatchDataset,
                                RunRequestRefused)
    from JBGWebUI import request_language, translator
    from JBGWebUIRun import run_in_progress, with_dataset_names

    def records(owner):
        """The owner's run records by run, for the configurations they recorded."""
        try:
            return {record.run.key: record for record in runs.owner_records(owner)}
        except Exception:
            return {}

    def stored(owner, pid, item, version=None):
        try:
            return configurations.stored_settings(owner, pid, item["configuration_id"],
                                                  version=version)
        except Exception:
            return None

    def details(principal, pid, item, record, schema, translate, language):
        owner = principal.principal_key
        run_id = item["run_id"]
        detail = {"item": item, "duration": duration_text(item, language), "winner": "",
                  "evaluation": None, "summary": None, "dark": [], "settings": None,
                  "roles": None, "rerunnable": item.get("kind", "training") in RERUNNABLE}
        try:
            overview = runs.overview(owner, RunReference(run_id))
            found = overview.get("results") or {}
            detail["evaluation"], detail["summary"] = found.get("evaluation"), found.get("summary")
        except Exception:
            pass
        if item.get("status") == "succeeded" and item.get("kind", "training") != "prediction":
            try:
                detail["winner"] = winning_pipeline(
                    results.detail(owner, run_id, "leaderboard", page=1, page_size=500))
            except Exception:
                pass
            try:
                detail["dark"] = [(i["target"], interval_text(i, language))
                                  for i in results.dark_number_summary(owner, run_id)]
            except Exception:
                pass
        # The settings it used against the configuration's current version.
        used = stored(owner, pid, item, item.get("configuration_version"))
        current = stored(owner, pid, item)
        if used is not None and current is not None:
            detail["settings"] = setting_differences(schema, used, current, translate, language)
        # Its column roles against the dataset's roles now.
        snapshot = ((record.spec or {}).get("configuration") if record is not None else None)
        if snapshot:
            try:
                now = inspection.get_roles(principal, pid, item["dataset_id"])
            except Exception:
                now = None
            if now is not None:
                detail["roles"] = role_differences(roles_from_snapshot(snapshot),
                                                   roles_from_dataset(now), translate, language)
        detail["snapshot"] = snapshot
        detail["used"] = used
        return detail

    @app.get("/ui/history", response_class=HTMLResponse, include_in_schema=False)
    def history(request: Request, run: str = "", kind: str = "", status: str = "",
                dataset: str = "", configuration: str = "",
                principal=Depends(principal_dependency)):
        owner = principal.principal_key
        project = active_project(request, owner)
        language = request_language(request)
        translate = translator(language)
        context = {"no_project": project is None, "items": [], "shown": [], "selected": None,
                   "compared": None, "filters": {"kind": kind, "status": status,
                                                 "dataset": dataset, "configuration": configuration},
                   "kinds": KINDS, "statuses": STATUSES, "tab_messages": MESSAGES,
                   "datasets_seen": [], "configurations_seen": []}
        if project is None:
            return render(request, principal, "history.html", "history", **context)
        pid = project["project_id"]
        try:
            items = with_dataset_names(runs.list_project_runs(owner, pid, limit=200), datasets,
                                       owner, pid, configurations=configurations)
        except Exception:
            items = []
        for item in items:
            item.setdefault("kind", "training")
            item["duration"] = duration_text(item, language)
        context["items"] = items
        context["datasets_seen"] = sorted({(i.get("dataset_id"), i.get("dataset_name") or "–")
                                           for i in items if i.get("dataset_id")},
                                          key=lambda pair: pair[1].lower())
        context["configurations_seen"] = sorted(
            {(i.get("configuration_id"), i.get("configuration_name") or "–")
             for i in items if i.get("configuration_id")}, key=lambda pair: pair[1].lower())
        shown = [i for i in items
                 if (not kind or i["kind"] == kind) and (not status or i["status"] == status)
                 and (not dataset or i.get("dataset_id") == dataset)
                 and (not configuration or i.get("configuration_id") == configuration)]
        context["shown"] = shown
        schema = configuration_schema(project["source"], translate, _server_template())
        by_run = {i["run_id"]: i for i in items}
        compare = [value for value in request.query_params.getlist("compare") if value in by_run]
        found = records(owner) if (run or compare) else {}
        if len(compare) == 2:
            left, right = (details(principal, pid, by_run[r], found.get(r), schema, translate,
                                   language) for r in compare)
            settings = (setting_differences(schema, left["used"], right["used"], translate, language)
                        if left["used"] is not None and right["used"] is not None else None)
            roles = (role_differences(roles_from_snapshot(left["snapshot"]),
                                      roles_from_snapshot(right["snapshot"]), translate, language)
                     if left["snapshot"] and right["snapshot"] else None)
            context["compared"] = {"left": left, "right": right, "settings": settings,
                                   "roles": roles}
        elif compare:
            context["compare_error"] = True              # not one or two: tick exactly two
        elif run in by_run:
            context["selected"] = details(principal, pid, by_run[run], found.get(run), schema,
                                          translate, language)
        context["can_rerun"] = not run_in_progress(runs, owner, pid)
        return render(request, principal, "history.html", "history", **context)

    @app.post("/ui/history/{run_id}/rerun", include_in_schema=False)
    def rerun(request: Request, run_id: str, principal=Depends(principal_dependency)):
        """Agreed 2026-11-24: the same configuration version and dataset."""
        owner = principal.principal_key
        project = active_project(request, owner)
        if project is None:
            return redirect("/ui/history")
        pid = project["project_id"]
        try:
            item = next(i for i in runs.list_project_runs(owner, pid, limit=200)
                        if i["run_id"] == run_id)
        except (StopIteration, Exception):
            return redirect("/ui/history", message="unavailable")
        kind = item.get("kind") or "training"
        if kind not in RERUNNABLE or not item.get("configuration_id"):
            return redirect("/ui/history", run=run_id, message="not_rerunnable")
        if run_in_progress(runs, owner, pid):
            return redirect("/ui/history", run=run_id, message="run_in_progress")
        try:
            created = project_runs.submit(principal, pid,
                                          configuration_id=item["configuration_id"],
                                          version=item.get("configuration_version"),
                                          dataset_id=item.get("dataset_id"),
                                          investigation=kind == "investigation")
        except InvestigationRefused:
            return redirect("/ui/history", run=run_id, message="groups_not_supported")
        except RunDoesNotMatchDataset:
            return redirect("/ui/history", run=run_id, message="not_fitting")
        except IdColumnNotInteger:
            return redirect("/ui/history", run=run_id, message="id_not_integer")
        except PermissionError:
            return redirect("/ui/history", run=run_id, message="signin_needed")
        except (RunRequestRefused, LookupError, ValueError, TypeError, OSError):
            return redirect("/ui/history", run=run_id, message="refused")
        return redirect("/ui/run", run=created["run_id"],
                        message="investigation_started" if kind == "investigation" else "started")
