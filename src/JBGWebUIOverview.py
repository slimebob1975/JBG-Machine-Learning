"""Overview tab of the web interface (revision 295d).

A first, simple overview of the open project (design decision 7: scoped to
the active project): the project, its active training dataset, the
configuration chosen for runs, the latest training and prediction runs and
the models. Each part links to the tab where it is changed; a part that is
not there yet says so and links to the tab that fills it. Without an open
project the page is empty apart from a hint. The title in the header links
here.

Read-only: the page only shows what the other tabs keep, through the same
services, and leaves out what a service cannot give.
"""
from __future__ import annotations

from fastapi import Depends, Request
from fastapi.responses import HTMLResponse


def add_overview_tab(app, *, principal_dependency, render, active_project, datasets=None,
                     configurations=None, runs=None, models=None, projects=None,
                     results=None) -> None:
    from JBGApplicationContracts import RunReference
    from JBGWebUIRun import STAGES

    def listed(service, owner, project_id):
        if service is None:
            return []
        try:
            return list(service.list(owner, project_id))
        except Exception:
            return []

    def latest_runs(owner, project_id):
        """The newest training and prediction run, with the training run's key figures."""
        if runs is None:
            return None, None, None
        try:
            items = runs.list_project_runs(owner, project_id, limit=200)
        except Exception:
            return None, None, None
        training = next((r for r in items if r.get("kind", "training") == "training"), None)
        prediction = next((r for r in items if r.get("kind") == "prediction"), None)
        evaluation = None
        if training is not None and training["status"] == "succeeded":
            try:
                results = runs.overview(owner, RunReference(training["run_id"]))["results"]
                evaluation = (results or {}).get("evaluation")
            except Exception:
                evaluation = None
        return training, prediction, evaluation

    def all_projects(request, owner, project):
        """299k (agreed 2026-11-13): key figures and charts over the owner's
        projects, and the open project's charts. Numbers only."""
        if runs is None or projects is None:
            return None
        from JBGOverviewStats import QUALITY_LABELS, overview_stats
        from JBGWebUI import request_language, translator
        from JBGWebUICharts import project_bars, quality_line, week_bars
        try:
            owned = projects.list(owner, limit=500)
            records = runs.owner_records(owner)
        except Exception:
            return None
        names = {p["project_id"]: p["name"] for p in owned}
        in_use = {pid: sum(1 for m in listed(models, owner, pid) if m.get("state") == "available")
                  for pid in names}
        open_id = project["project_id"] if project is not None else None
        stats = overview_stats(records, project_names=names, open_project=open_id,
                               models_in_use=in_use)
        if open_id is not None and configurations is not None:                # 300r
            from JBGWebUIRun import configuration_names, with_configuration_names
            with_configuration_names(stats["latest"],
                                     configuration_names(configurations, owner, open_id))
        language = request_language(request)
        _ = translator(language)

        def week_label(week):
            return f"{_('w.')} {week.isocalendar()[1]}"
        metric = stats["quality_metric"]
        metric_label = _(QUALITY_LABELS.get(metric, "The configurations' metrics")) if metric != "" \
            else _("The configurations' metrics")
        charts = {
            "per_week": week_bars(
                stats["per_week"], [("succeeded", "chart-ok", _("Succeeded")),
                                    ("failed", "chart-fail", _("Failed"))],
                label=_("Runs per week"), empty=_("No finished runs in the last 12 weeks."),
                week_label=week_label, language=language),
            "per_project": project_bars(
                stats["per_project"], label=_("Rows processed per project"),
                empty=_("No rows recorded yet. Runs record them from now on."),
                language=language),
        }
        if open_id is not None:
            charts["quality"] = quality_line(
                stats["quality"], stats["quality_average"],
                label=_("Model quality per training run") + f" ({metric_label})",
                empty=_("No finished training runs with an evaluation yet."),
                average_label=_("Average of the last three"),
                point_label=lambda p: p["created_at"].strftime("%Y-%m-%d"), language=language)
            charts["rows_per_week"] = week_bars(
                stats["rows_per_week"], [("rows", "chart-bar", _("Rows"))],
                label=_("Rows processed per week"),
                empty=_("No rows recorded yet. Runs record them from now on."),
                week_label=week_label, language=language)
        return {"stats": stats, "charts": charts, "metric_label": metric_label}

    def run_resources(owner, pid, count=10):
        """301w: the open project's latest runs with their peak memory, peak
        processes and duration (runs before 301w have no samples)."""
        if runs is None or results is None:
            return []
        from JBGWebUIRun import with_dataset_names
        try:
            items = with_dataset_names(runs.list_project_runs(owner, pid, limit=count),
                                       datasets, owner, pid)
        except Exception:
            return []
        for item in items:
            try:
                item["resources"] = results.resources(owner, item["run_id"])["summary"]
            except Exception:
                item["resources"] = None
        return items

    @app.get("/ui/overview", response_class=HTMLResponse, include_in_schema=False)
    def overview_tab(request: Request, principal=Depends(principal_dependency)):
        owner = principal.principal_key
        project = active_project(request, owner)
        context = {"no_project": project is None, "dataset_count": 0,
                   "configuration_count": 0, "latest_training": None,
                   "latest_prediction": None, "evaluation": None, "model_count": 0,
                   "available_count": 0, "newest_model": None, "stages": STAGES,
                   "has_runs": runs is not None, "has_models": models is not None,
                   "has_configurations": configurations is not None,
                   "has_datasets": datasets is not None}
        if project is not None:
            pid = project["project_id"]
            context["resources"] = run_resources(owner, pid)                   # 301w
            context["dataset_count"] = len(listed(datasets, owner, pid))
            context["configuration_count"] = len(listed(configurations, owner, pid))
            (context["latest_training"], context["latest_prediction"],
             context["evaluation"]) = latest_runs(owner, pid)
            if configurations is not None:                                    # 300r
                from JBGWebUIRun import configuration_names, with_configuration_names
                with_configuration_names(
                    [r for r in (context["latest_training"], context["latest_prediction"]) if r],
                    configuration_names(configurations, owner, pid))
            items = listed(models, owner, pid)
            context["model_count"] = len(items)
            context["available_count"] = sum(1 for m in items if m.get("state") == "available")
            context["newest_model"] = items[0] if items else None
        context["all"] = all_projects(request, owner, project)                # 299k
        return render(request, principal, "overview.html", "overview", **context)
