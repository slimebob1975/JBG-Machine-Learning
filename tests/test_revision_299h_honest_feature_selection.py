"""299h (agreed 2026-11-13): the Configuration tab's feature selection section
had no effect in web runs (only Voila's interface reads its settings). Its
settings are no longer shown or read by the form, and stay stored as they
are; the section says what chooses the variables (the column roles), and the
pipeline picture says so too. The investigation returns as a run (299i).
"""
import re
from datetime import timedelta

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("jinja2")

from JBGDatasetRoles import DatasetRoles  # noqa: E402
from test_revision_292a_configuration_tab import _as_form, _form_for  # noqa: E402
from test_revision_298e_pipeline_picture import _steps  # noqa: E402


def _schema(language="sv"):
    from JBGConfigSchema import configuration_schema
    from JBGConfigurationService import _server_template
    from JBGWebUI import translator
    return configuration_schema("csv", translator(language), _server_template())


def test_the_sections_fields_are_inactive_and_the_group_stays():
    schema = _schema()
    inactive = [f["key"] for f in schema["fields"] if f.get("inactive")]
    assert "mode.feature_selection_mode" in inactive and "mode.feature_search_trials" in inactive
    assert all(f["group"] == "feature_selection" for f in schema["fields"] if f.get("inactive"))
    assert "feature_selection" in [g["key"] for g in schema["groups"]]
    # Dimensionality reduction (mode.feature_selection) is used by the engine.
    assert not next(f for f in schema["fields"] if f["key"] == "mode.feature_selection").get("inactive")


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


def test_the_form_neither_shows_nor_resets_the_stored_settings(tmp_path):
    from JBGIdentity import AuthenticatedPrincipal, AuthenticationMode
    owner = AuthenticatedPrincipal(AuthenticationMode.LOCAL, "developer").principal_key
    with _client(tmp_path) as client:
        location = client.post("/ui/projects", data={"name": "P", "source": "csv"},
                               follow_redirects=False).headers["location"]
        project = re.search(r"selected=([0-9a-f-]{36})", location).group(1)
        client.post(f"/ui/projects/{project}/open")
        configuration = client.post(f"/api/projects/{project}/configurations",
                                    json={"name": "C"}).json()["configuration_id"]
        service = client.app.state.jbg["configuration_service"]
        service.save(owner, project, configuration, expected_version=1, settings={"mode": {
            "feature_selection_mode": "assisted", "feature_search_preset": "Custom",
            "feature_search_trials": 3}})
        page = client.get(f"/ui/configuration?configuration={configuration}").text
        assert "f:mode.feature_selection_mode" not in page and "f:mode.feature_search_trials" not in page
        assert "väljs variablerna med kolumnrollerna på fliken Dataset" in page
        assert "f:mode.feature_selection" in page                     # reduction stays
        schema = _schema()
        values = service.get(owner, project, configuration)["settings"]
        shown = {"fields": [f for f in schema["fields"] if not f.get("inactive")]}
        form = _form_for(values, shown) + [("expected_version", "2")]
        saved = client.post(f"/ui/configuration/{configuration}", data=_as_form(form),
                            follow_redirects=False)
        errors = re.findall(r"class=\"field-error[^>]*>([^<]*)", saved.text)
        assert saved.status_code == 303, (errors, re.findall(r"message error[^>]*>([^<]*)", saved.text))
        assert "message=saved" in saved.headers["location"]
        stored = service.get(owner, project, configuration)
        assert stored["version"] == 3
        assert stored["settings"]["mode"]["feature_selection_mode"] == "assisted"
        assert stored["settings"]["mode"]["feature_search_trials"] == 3


def test_the_pipeline_picture_tells_what_chooses_the_variables():
    steps, _ = _steps(roles=None)
    assert steps["feature_selection"]["subtitle"] == "Kolumnroller"
    roles = DatasetRoles.from_mapping({"id": "id", "a": "numeric", "b": "text", "c": "ignored",
                                       "d": "class"})
    steps, _ = _steps(roles=roles)
    assert steps["feature_selection"]["subtitle"] == "Kolumnroller: 2 variabler"
    assert steps["feature_selection"]["state"] == "used"
    steps, _ = _steps(roles=roles, language="en")
    assert steps["feature_selection"]["subtitle"] == "Column roles: 2 variables"


def test_the_backlog_keeps_the_semicolon_item():
    from pathlib import Path
    backlog = (Path(__file__).resolve().parent.parent / "BACKLOG.md").read_text(encoding="utf-8")
    assert "semicolon" in backlog and "299f2" in backlog
