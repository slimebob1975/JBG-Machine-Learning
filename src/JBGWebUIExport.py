"""301p (asked 2026-11-26): every view's and subview's tables as CSV or Excel.

A view is exported by asking for its own address with ``export=csv`` or
``export=xlsx``: the tab builds the same content as for the page, and
``render`` hands it here instead of drawing the page. An exporter per template
turns the content into tables, each with a title, column names and rows
(decided 2026-11-26):

- Excel: one sheet per table;
- CSV: the tables one after another, each with its title on a row of its own
  and an empty row between them; semicolons, UTF-8 with a byte-order mark and
  decimal commas, as Swedish Excel reads them;
- all rows, also those shown a page at a time.
"""
from __future__ import annotations

import csv
import io
import re
from datetime import datetime
from urllib.parse import quote

FORMATS = ("csv", "xlsx")


def _cell(value, comma: bool):
    if isinstance(value, bool):
        return "Ja" if value else "Nej"
    if isinstance(value, float):
        text = repr(value) if value != int(value) or abs(value) >= 1e15 else str(int(value))
        return text.replace(".", ",") if comma else text
    if value is None:
        return ""
    return value


def tables_to_csv(tables: list, comma: bool = True) -> bytes:
    out = io.StringIO(newline="")
    writer = csv.writer(out, delimiter=";", lineterminator="\r\n")
    for i, table in enumerate(tables):
        if i:
            writer.writerow([])
        writer.writerow([table["title"]])
        writer.writerow(table["columns"])
        for row in table["rows"]:
            writer.writerow([_cell(v, comma) for v in row])
    return out.getvalue().encode("utf-8-sig")


def _sheet_name(title: str, used: set) -> str:
    name = re.sub(r"[\[\]:*?/\\]", "-", title).strip()[:31] or "Tabell"
    base, n = name, 2
    while name.lower() in used:
        suffix = f" ({n})"
        name, n = base[:31 - len(suffix)] + suffix, n + 1
    used.add(name.lower())
    return name


def tables_to_xlsx(tables: list) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font
    book = Workbook()
    book.remove(book.active)
    used = set()
    for table in tables or [{"title": "Tom", "columns": [], "rows": []}]:
        sheet = book.create_sheet(_sheet_name(table["title"], used))
        sheet.append([str(c) for c in table["columns"]])
        for cell in sheet[1]:
            cell.font = Font(bold=True)
        for row in table["rows"]:
            sheet.append([v if isinstance(v, (int, float, str)) or v is None else str(v)
                          for v in row])
        for column in sheet.columns:
            width = max((len(str(c.value)) for c in column if c.value is not None), default=8)
            sheet.column_dimensions[column[0].column_letter].width = min(60, max(8, width + 2))
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def _response(tables: list, form: str, name: str):
    from fastapi.responses import Response
    stamp = datetime.now().strftime("%Y-%m-%d")
    filename = f"{name} {stamp}.{form}"
    plain = "".join(c if c.isascii() and (c.isalnum() or c in "._- ") else "_" for c in filename)
    if form == "xlsx":
        body = tables_to_xlsx(tables)
        kind = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        body = tables_to_csv(tables)
        kind = "text/csv; charset=utf-8"
    return Response(body, media_type=kind, headers={
        "Content-Disposition": f'attachment; filename="{plain}"; '
                               f"filename*=UTF-8''{quote(filename)}"})


def export_response(request, template: str, context: dict):
    """The file for an export request, or None (then the page is drawn)."""
    form = request.query_params.get("export", "")
    if form not in FORMATS:
        return None
    exporter = EXPORTERS.get(template)
    if exporter is None:
        return None
    _ = context.get("_") or (lambda text: text)
    found = exporter(context, _)
    if found is None:
        return None
    name, tables = found
    return _response(tables, form, name)


def exportable(template: str, context: dict) -> bool:
    """301r: whether the view has a table with at least one row to export."""
    exporter = EXPORTERS.get(template)
    if exporter is None:
        return False
    _ = context.get("_") or (lambda text: text)
    try:
        found = exporter(context, _)
    except Exception:
        return False
    return bool(found) and any(t.get("rows") for t in found[1])


def table(title: str, columns: list, rows: list) -> dict:
    return {"title": title, "columns": list(columns), "rows": [list(r) for r in rows]}


def _detail_table(title: str, detail: dict) -> dict:
    columns = detail.get("headings") or detail.get("columns") or []
    return table(title, columns, detail.get("rows") or [])


# --- Results ---------------------------------------------------------------------------

def _results(context: dict, _) -> tuple | None:
    view = context.get("view") or "overview"
    run = (context.get("selected_run") or "")[:8]
    overview = context.get("overview") or {}
    found = overview.get("results") or {}
    tables = []
    if context.get("is_investigation"):
        investigation = context.get("investigation") or {}
        rows = [[k, v] for k, v in investigation.items() if not isinstance(v, (list, dict))]
        tables.append(table(_("Recommendation"), [_("Setting"), _("Value")], rows))
        return f"{_('Results')} {run} {_('Feature investigation')}", tables
    if view == "overview":
        ev = found.get("evaluation") or {}
        tables.append(table(_("Evaluation on test data"), [_("Measure"), _("Value")], [
            [_("Accuracy"), ev.get("accuracy")], [_("Balanced accuracy"), ev.get("balanced_accuracy")],
            ["MCC", ev.get("mcc")], ["F1 (macro)", ev.get("f1_macro")],
            [f"F1 ({_('weighted')})", ev.get("f1_weighted")]]))
        matrix = ev.get("confusion_matrix") or []
        labels = context.get("labels") or []
        if matrix:
            names = labels if len(labels) == len(matrix) else [str(i) for i in range(len(matrix))]
            tables.append(table(_("Confusion matrix"), [_("Actual class")] + list(names),
                                [[names[i]] + list(row) for i, row in enumerate(matrix)]))
        summary = found.get("summary") or {}
        if summary:
            tables.append(table(_("Summary"), [_("Measure"), _("Value")],
                                [[k, v] for k, v in summary.items()
                                 if not isinstance(v, (list, dict))]))
        return f"{_('Results')} {run} {_('Overview')}", tables
    detail = context.get("detail")
    if view != "dark_numbers":
        if not detail:
            return None
        titles = {"leaderboard": _("Model comparison"), "mispredictions": _("Mispredictions"),
                  "importance": _("Feature importance")}
        title = titles.get(view, view)
        return f"{_('Results')} {run} {title}", [_detail_table(title, detail)]
    # Dark Numbers: everything the view shows (asked 2026-11-26).
    estimates = context.get("dark_estimates") or {}
    reasons = context.get("dark_reasons") or {}
    record = context.get("dark_record") or {}
    settings = []
    method = record.get("method") or {}
    for key, value in method.items():
        settings.append([f"{_('Method')}: {key}", value])
    for key, value in (record.get("parameters") or {}).items():
        settings.append([key, value if not isinstance(value, (list, dict)) else str(value)])
    if settings:
        tables.append(table(_("Settings"), [_("Setting"), _("Value")], settings))
    share_rows, growth_rows = [], []
    for interval in context.get("dark_summary") or []:
        target = interval.get("target")
        for p in interval.get("points") or []:
            label = _(estimates.get(p.get("label"), p.get("label")))
            share_rows.append([target, label, p.get("value"),
                               "" if p.get("value") is not None
                               else _(reasons.get(p.get("reason"), p.get("reason") or ""))])
            if p.get("growth") is not None:
                growth_rows.append([target, label, p.get("value"), p.get("growth"),
                                    1 + p.get("growth"), p.get("hidden"),
                                    p.get("registered_target"), p.get("registered_rest"),
                                    p.get("growth") / (1 + p.get("growth"))])
    if share_rows:
        tables.append(table(_("Estimates"), [_("Target class"), _("Estimate"),
                                              _("Estimated Dark Number"), _("Reason")], share_rows))
    if growth_rows:
        tables.append(table(_("Growth"), [_("Target class"), _("Estimate"),
                                           _("Estimated Dark Number"), _("Growth of the target class"),
                                           _("Factor"), _("Hidden"), _("Registered in the target class"),
                                           _("Registered as another class"),
                                           _("Missing from the register")], growth_rows))
    if detail:
        tables.append(_detail_table(_("Calculations"), detail))
    matrix = context.get("dark_matrix")
    if matrix:
        tables.append(_detail_table(_("Confusion matrices"), matrix))
    return f"{_('Results')} {run} {_('Dark Numbers')}", tables


# --- The other tabs ----------------------------------------------------------------------

def _records(title: str, items, fields: list, _) -> dict:
    """A table of chosen fields (key, heading) of a list of objects."""
    items = list(items or [])
    return table(title, [_(heading) for _key, heading in fields],
                 [[item.get(key) if isinstance(item, dict) else getattr(item, key, None)
                   for key, _heading in fields] for item in items])


RUN_FIELDS = [("created_at", "Started"), ("finished_at", "Finished"), ("kind", "Kind"),
              ("status", "Status"), ("dataset_name", "Dataset"),
              ("configuration_name", "Configuration"), ("configuration_version", "Version"),
              ("run_id", "Run")]


def _evaluation_rows(ev: dict, _) -> list:
    return [[_("Accuracy"), ev.get("accuracy")], [_("Balanced accuracy"), ev.get("balanced_accuracy")],
            ["MCC", ev.get("mcc")], ["F1 (macro)", ev.get("f1_macro")],
            [f"F1 ({_('weighted')})", ev.get("f1_weighted")]]


def _dataset(context: dict, _):
    selected = context.get("selected") or {}
    view = context.get("view") or "preview"
    tables = [_records(_("Datasets"), context.get("datasets"), [
        ("name", "Name"), ("role", "Role"), ("source", "Source"),
        ("validation_state", "Validation"), ("active_training", "Active for training"),
        ("created_at", "Created"), ("updated_at", "Changed")], _)]
    data = context.get("data") or {}
    if selected and data:
        if view == "preview" and data.get("rows") is not None:
            names = [c.get("name") if isinstance(c, dict) else c for c in data.get("columns") or []]
            tables.append(table(_("Preview"), names, data.get("rows") or []))
        elif view == "profile":
            tables.append(_records(_("Profile"), data.get("columns"), [
                ("name", "Column"), ("type", "Type"), ("missing_share", "Missing"),
                ("distinct", "Distinct values")], _))
        elif view == "classes":
            rows = [[c.get("value"), c.get("count"), c.get("share")] for c in data.get("classes") or []]
            if data.get("missing"):
                rows.append([_("Missing"), data.get("missing"), None])
            tables.append(table(_("Classes"), [_("Class"), _("Count"), _("Share")], rows))
        elif view == "roles":
            roles = context.get("roles") or {}
            tables.append(table(_("Column roles"), [_("Column"), _("Role")],
                                [[name, roles.get(name, "")] for name in
                                 [c.get("name") for c in data.get("columns") or []]]))
    titles = {"preview": "Preview", "profile": "Profile", "classes": "Classes",
              "roles": "Column roles", "visualisation": "Visualisation"}
    name = selected.get("name") or ""
    return f"{_('Dataset')} {name} {_(titles.get(view, view))}".strip(), tables


def _run(context: dict, _):
    tables = [_records(_("Runs"), context.get("recent"), RUN_FIELDS, _)]
    overview = context.get("overview") or {}
    ev = (overview.get("results") or {}).get("evaluation") or {}
    if ev:
        tables.append(table(_("Evaluation on test data"), [_("Measure"), _("Value")],
                            _evaluation_rows(ev, _)))
    return _("Training"), tables


def _models(context: dict, _):
    tables = [_records(_("Models"), context.get("models"), [
        ("name", "Name"), ("state", "Status"), ("created_at", "Created"),
        ("configuration_name", "Configuration"), ("model_id", "Model")], _)]
    card = context.get("card") or {}
    ev = card.get("evaluation") or {}
    if ev:
        tables.append(table(_("Evaluation on test data"), [_("Measure"), _("Value")],
                            _evaluation_rows(ev, _)))
    if card.get("predictions"):
        tables.append(_records(_("Prediction runs"), card["predictions"], RUN_FIELDS, _))
    return _("Models"), tables


def _prediction(context: dict, _):
    tables = []
    predictions = context.get("predictions")
    if predictions:
        tables.append(_detail_table(_("Predictions"), predictions))
    tables.append(_records(_("Prediction runs"), context.get("recent"), RUN_FIELDS, _))
    return _("Prediction"), tables


def _history(context: dict, _):
    tables = [_records(_("Runs"), context.get("shown"), RUN_FIELDS + [("duration", "Duration")], _)]
    selected, compared = context.get("selected"), context.get("compared")

    def details(title, d):
        ev = d.get("evaluation") or {}
        rows = [[_("Winning pipeline"), d.get("winner")], [_("Duration"), d.get("duration")]]
        rows += _evaluation_rows(ev, _) if ev else []
        rows += [[f"{_('Estimated Dark Number')} · {target}", interval]
                 for target, interval in d.get("dark") or []]
        return table(title, [_("Measure"), _("Value")], rows)
    if compared:
        left, right = compared["left"], compared["right"]
        tables += [details(f"{_('Run')} 1", left), details(f"{_('Run')} 2", right)]
        for key, title in (("settings", "Settings that differ"), ("roles", "Column roles that differ")):
            if compared.get(key):
                tables.append(table(_(title), [_("Setting"), f"{_('Run')} 1", f"{_('Run')} 2"],
                                    compared[key]))
    elif selected:
        tables.append(details(_("Run"), selected))
        for key, title in (("settings", "Settings against the configuration's current version"),
                           ("roles", "Column roles against the dataset's current roles")):
            if selected.get(key):
                tables.append(table(_(title), [_("Setting"), _("This run"), _("Now")],
                                    selected[key]))
    return _("Run History"), tables


def _overview(context: dict, _):
    stats = ((context.get("all") or {}).get("stats") or {})
    return _("Overview"), [_records(_("Latest runs"), stats.get("latest"), [
        ("created_at", "Started"), ("status", "Status"), ("configuration_name", "Configuration"),
        ("configuration_version", "Version"), ("run_id", "Run")], _)]


def _configuration(context: dict, _):
    tables = [_records(_("Configurations"), context.get("items"), [
        ("name", "Name"), ("version", "Version"), ("updated_at", "Changed"),
        ("configuration_id", "Configuration")], _)]
    values = context.get("values") or {}
    fields = (context.get("schema") or {}).get("fields") or []
    if values and fields:
        from JBGWebUIHistory import value_text
        language = context.get("language", "sv")
        rows = []
        for field in fields:
            if field.get("kind") == "parameters":
                continue
            section, name = field["key"].split(".", 1)
            options = {o["value"]: o["label"] for o in field.get("options") or []}
            rows.append([field["label"], value_text((values.get(section) or {}).get(name), _,
                                                     language, options)])
        tables.append(table(_("Settings"), [_("Setting"), _("Value")], rows))
    return _("Configuration"), tables


def _projects(context: dict, _):
    return _("Projects"), [_records(_("Projects"), context.get("projects"), [
        ("name", "Name"), ("source", "Source"), ("created_at", "Created"),
        ("project_id", "Project")], _)]


EXPORTERS = {"results.html": _results, "dataset.html": _dataset, "run.html": _run,
             "models.html": _models, "prediction.html": _prediction,
             "history.html": _history, "overview.html": _overview,
             "configuration.html": _configuration, "projects.html": _projects}
