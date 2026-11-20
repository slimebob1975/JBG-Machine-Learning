"""300o (reported 2026-11-20): after 300n an older configuration could not be
changed: the Configuration tab showed the new settings empty and saving
failed (KeyError). Config.LATER_KEYS gave defaults only when a run loaded the
configuration; the configuration service now fills them in too, when it shows
stored settings and when it saves a change."""
import json
import tempfile
from pathlib import Path

from sqlalchemy import select, update

from Config import Config
from JBGConfigSchema import configuration_schema
from JBGConfigurationService import _server_template, with_later_defaults
from JBGIdentity import AuthenticatedPrincipal, AuthenticationMode
from JBGWebUI import translator
from test_revision_288a_project_runs import _client, _setup
from test_revision_292a_configuration_tab import _as_form, _form_for

OWNER = AuthenticatedPrincipal(AuthenticationMode.LOCAL, "developer").principal_key


def test_every_later_key_is_filled_in():
    settings = {"mode": {}, "io": {}}
    filled = with_later_defaults(settings)
    assert filled["mode"] == Config.LATER_KEYS["mode"] and settings["mode"] == {}


def test_an_older_configuration_shows_the_defaults_and_saves(tmp_path):
    with _client(tmp_path) as client:
        project, dataset, configuration = _setup(client)
        client.post(f"/ui/projects/{project}/open")
        service = client.app.state.jbg["configuration_service"]
        repository = service._repository
        later = list(Config.LATER_KEYS["mode"])
        with repository._engine.begin() as connection:                   # as saved before
            for row in connection.execute(select(repository._revisions)).mappings().all():
                settings = json.loads(row["settings_json"])
                for key in later:
                    settings["mode"].pop(key, None)
                connection.execute(update(repository._revisions).where(
                    (repository._revisions.c.configuration_id == row["configuration_id"])
                    & (repository._revisions.c.version == row["version"])).values(
                    settings_json=json.dumps(settings)))
        page = client.get(f"/ui/configuration?configuration={configuration}").text
        assert 'name="f:mode.dark_number_c_max" value="10.0"' in page
        assert 'name="f:mode.dark_number_flip_repeats" value="2"' in page
        current = service.get(OWNER, project, configuration)
        schema = configuration_schema("csv", translator("sv"), _server_template())
        shown = {"fields": [f for f in schema["fields"] if not f.get("inactive")]}
        values = current["settings"]
        values["mode"]["dark_number_flip_repeats"] = 5
        form = _form_for(values, shown) + [("expected_version", str(current["version"]))]
        saved = client.post(f"/ui/configuration/{configuration}", data=_as_form(form),
                            follow_redirects=False)
        assert saved.status_code == 303 and "message=saved" in saved.headers["location"]
        stored = service.get(OWNER, project, configuration)["settings"]["mode"]
        assert stored["dark_number_flip_repeats"] == 5 and stored["dark_number_c_max"] == 10.0
