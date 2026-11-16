"""299j (agreed 2026-11-13): a feature investigation's recommendation on the
Results tab, and "Use the recommendation", which fills the dataset's column
roles form (the columns left out become Ignored; a date column only when all
its derived variables were left out). Nothing is saved until "Save column
roles". Refused, with the reason, when the roles have changed since the
investigation or the recommendation keeps every variable. Also: the status of
the followed run in the run list updates while the run goes on.
"""
import json
import re
from datetime import timedelta

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("jinja2")

from JBGApplicationContracts import DataSourceKind, RunStatus  # noqa: E402
from JBGDatasetRoles import DatasetRoles  # noqa: E402
from JBGIdentity import AuthenticatedPrincipal, AuthenticationMode  # noqa: E402
from JBGRunInvestigation import recommendation_plan, result_view  # noqa: E402
from test_revision_288a_project_runs import _setup  # noqa: E402

OWNER = AuthenticatedPrincipal(AuthenticationMode.LOCAL, "developer").principal_key


def _saved(original, selected, **extra):
    saved = {"original_columns": original,
             "recommendation": {"selected_columns": selected,
                                "excluded_columns": [c for c in original if c not in selected],
                                "model_type": "Linear", "search_mean_mcc": 0.7,
                                "search_std_mcc": 0.05},
             "nested_validation": {"selected": {"mean_mcc": 0.61, "std_mcc": 0.04},
                                   "full_baseline": {"mean_mcc": 0.58, "std_mcc": 0.06}},
             "target": "a", "options": {"outer_folds": 3, "max_evaluations": 30},
             "evaluated_subsets": 12, "development_rows": 108}
    saved.update(extra)
    return saved


ROLES = DatasetRoles.from_mapping({"row_id": "id", "target": "class", "f1": "numeric",
                                   "f2": "numeric", "note": "text", "when": "date",
                                   "other": "ignored"})


# --- The plan ----------------------------------------------------------------------------

def test_left_out_columns_become_ignored_and_a_date_only_when_all_its_parts_are():
    derived = ["when_year", "when_month_sin", "when_month_cos", "when_weekday_sin",
               "when_weekday_cos", "when_missing"]
    all_out = recommendation_plan(_saved(["f1", "f2", "note"] + derived, ["f1"]), ROLES)
    assert all_out["reason"] is None and all_out["ignore"] == ["f2", "note", "when"]
    assert all_out["roles"]["f2"] == "ignored" and all_out["roles"]["f1"] == "numeric"
    assert all_out["roles"]["other"] == "ignored" and all_out["roles"]["row_id"] == "id"
    partly = recommendation_plan(_saved(["f1", "f2", "note"] + derived, ["f1", "when_year"]),
                                 ROLES)
    assert partly["ignore"] == ["f2", "note"]                       # the date stays
    direct = recommendation_plan(_saved(["f1", "f2", "note", "when"], ["f1", "f2", "note"]),
                                 ROLES)
    assert direct["ignore"] == ["when"]


def test_changed_roles_and_keeping_everything_are_refused():
    changed = recommendation_plan(_saved(["f1", "f2", "gone"], ["f1"]), ROLES)
    assert changed["reason"] == "roles_changed"
    assert changed["mismatch"] == ["note", "when", "gone"]
    everything = recommendation_plan(_saved(["f1", "f2", "note", "when"],
                                            ["f1", "f2", "note", "when"]), ROLES)
    assert everything["reason"] == "keeps_all" and everything["ignore"] == []
    assert recommendation_plan({}, ROLES)["reason"] == "unreadable"


def test_the_view_reads_only_what_it_shows():
    view = result_view(_saved(["f1", "f2"], ["f1"],
                              one_vs_rest={"target": "a", "rest_label": "(other classes)"}))
    assert view["selected"] == ["f1"] and view["excluded"] == ["f2"] and view["one_vs_rest"]
    assert view["selected_score"]["mean_mcc"] == 0.61 and view["baseline_score"]["std_mcc"] == 0.06
    assert view["search_score"]["mean_mcc"] == 0.7 and view["outer_folds"] == 3
    assert result_view({"recommendation": "x", "nested_validation": None})["selected"] == []


# --- The pages ---------------------------------------------------------------------------

def _client(tmp_path):
    from fastapi.testclient import TestClient
    from JBGFastAPIServer import create_server_app
    from JBGMetadataStore import MetadataStoreSettings
    from JBGSQLServer import SQLServerSettings
    return TestClient(create_server_app(
        settings=MetadataStoreSettings(sqlite_path=tmp_path / "jobs.sqlite"),
        run_logs=tmp_path / "run-logs", csv_root=tmp_path / "csv", model_root=tmp_path / "models",
        results_root=tmp_path / "runs", sql_server=SQLServerSettings(),
        dispatcher_options={"poll_seconds": 60, "heartbeat_seconds": 1,
                            "stale_after": timedelta(minutes=5)}))


def _investigation(client, tmp_path, project, dataset, saved, status=RunStatus.SUCCEEDED):
    store = client.app.state.jbg["store"]
    run = store.create(OWNER, DataSourceKind.CSV, {"spec_version": 1, "project_run": {
        "project_id": project, "kind": "investigation", "dataset_id": dataset,
        "configuration_name": "Standard", "configuration_version": 1}})
    store.claim(run, "w")
    if status is RunStatus.SUCCEEDED:
        folder = tmp_path / "runs" / project / run.key
        folder.mkdir(parents=True)
        (folder / "investigation.json").write_text(json.dumps(saved), encoding="utf-8")
        store.finish(run, "w", RunStatus.SUCCEEDED, result={"schema_version": 1,
                                                            "kind": "investigation"})
    return run.key


def _opened(client):
    project, dataset, configuration = _setup(client)
    client.post(f"/ui/projects/{project}/open")
    return project, dataset


def test_the_results_tab_shows_the_recommendation_and_offers_to_use_it(tmp_path):
    with _client(tmp_path) as client:
        project, dataset = _opened(client)
        run = _investigation(client, tmp_path, project, dataset, _saved(["f1", "f2"], ["f1"]))
        page = client.get(f"/ui/results?run={run}").text
        assert "Variabelundersökning" in page and "subtabs" not in page.split("<aside")[1]
        assert "1 av 2 variabler" in page and "0,61 ± 0,04" in page and "0,58 ± 0,06" in page
        assert re.search(r"<h3>Utelämnade</h3>\s*<ul><li>f2</li>", page)
        link = f"/ui/dataset?dataset={dataset}&view=roles&recommendation={run}"
        assert f'<a class="btn act ready" href="{link}">Använd rekommendationen</a>' in page


def test_refusals_say_why(tmp_path):
    with _client(tmp_path) as client:
        project, dataset = _opened(client)
        everything = _investigation(client, tmp_path, project, dataset,
                                    _saved(["f1", "f2"], ["f1", "f2"]))
        page = client.get(f"/ui/results?run={everything}").text
        assert ('title="Rekommendationen behåller alla variabler, så det finns inget att '
                'ändra.">Använd rekommendationen</button>') in page
        changed = _investigation(client, tmp_path, project, dataset,
                                 _saved(["f1", "f2", "f9"], ["f1"]))
        page = client.get(f"/ui/results?run={changed}").text
        assert "Kolumner som skiljer sig: f9" in page and "btn act blocked" in page
        broken = _investigation(client, tmp_path, project, dataset, {})
        (tmp_path / "runs" / project / broken / "investigation.json").write_text("{", "utf-8")
        assert "Undersökningens resultat kan inte läsas." in client.get(
            f"/ui/results?run={broken}").text


def test_using_it_fills_the_roles_form_and_saves_nothing(tmp_path):
    with _client(tmp_path) as client:
        project, dataset = _opened(client)
        run = _investigation(client, tmp_path, project, dataset, _saved(["f1", "f2"], ["f1"]))
        page = client.get(f"/ui/dataset?dataset={dataset}&view=roles&recommendation={run}").text
        assert "Ifyllt från variabelundersökningens rekommendation" in page
        assert "Ändrade: f2" in page
        row = re.search(r'<tr class="changed"><td>f2</td>.*?</tr>', page, re.S).group(0)
        assert '<option value="ignored" selected>' in row
        assert "data-wait-dirty" in page                             # ready to save
        repository = client.app.state.jbg["datasets"]
        assert repository.get_roles(OWNER, project, dataset).as_mapping()["f2"] == "numeric"
        other = client.get(f"/ui/dataset?dataset={dataset}&view=roles&recommendation=nope").text
        assert "Ifyllt från variabelundersökningens" not in other


def test_the_run_list_status_follows_the_run(tmp_path):
    from JBGWebUI import WEB
    script = (WEB / "static" / "jbg.js").read_text(encoding="utf-8")
    assert "data-run-status" in script and "labels[overview.status]" in script
    with _client(tmp_path) as client:
        project, dataset = _opened(client)
        client.post("/ui/configuration/" + client.get(
            f"/api/projects/{project}/configurations").json()[0]["configuration_id"] + "/select")
        run = _investigation(client, tmp_path, project, dataset, {}, status=RunStatus.RUNNING)
        page = client.get(f"/ui/run?run={run}").text
        assert re.search(f'<td data-run-status="{run}"><span class="badge [^"]*">Körs</span>', page)
        assert f'data-run-poll="{run}"' in page


def test_the_new_texts_are_translated():
    import JBGWebUI
    from JBGWebUIResults import RECOMMENDATION_REASONS
    catalog = JBGWebUI._load_catalog("sv")
    assert all(text in catalog for text in RECOMMENDATION_REASONS.values())
    template = (JBGWebUI.WEB / "templates" / "results.html").read_text(encoding="utf-8")
    block = template.split("299j: a feature investigation's recommendation.")[1].split("{% elif")[0]
    for text in re.findall(r'_\("([^"]+)"\)', block):
        assert text in catalog, text
