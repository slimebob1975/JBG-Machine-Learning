"""300h (reported 2026-11-19): in a CSV project, a notification address set in
the configuration (and the server's SMTP setting) never reached the run: the
CSV preparation clears the address so the saved, shared model artifact never
carries it, and the run kept that cleared copy; the worker's CSV check also
rejected any address. The run now keeps the e-mail settings; the artifact
still does not carry the address, and SQL identity is still refused."""
import json
from types import SimpleNamespace

import pytest

from JBGIdentity import AuthenticatedPrincipal, AuthenticationMode
from test_revision_288a_project_runs import _client, _setup

OWNER = AuthenticatedPrincipal(AuthenticationMode.LOCAL, "developer").principal_key


def test_a_csv_run_keeps_the_address_and_the_server(tmp_path, monkeypatch):
    monkeypatch.setenv("DEFAULT_SMTP_SERVER", "smtp.example.org")
    monkeypatch.setenv("DEFAULT_NOTIFICATION_EMAIL", "")
    with _client(tmp_path) as client:
        project, dataset, configuration = _setup(client)
        service = client.app.state.jbg["configuration_service"]
        current = service.get(OWNER, project, configuration)
        service.save(OWNER, project, configuration, expected_version=current["version"],
                     settings={"mail": {"notification_email": "me@example.org"}})
        created = client.post(f"/api/projects/{project}/runs",
                              json={"configuration_id": configuration})
        assert created.status_code == 201
        spec = client.app.state.jbg["store"].list_for_owner(OWNER)[0].spec
        assert spec["configuration"]["mail"] == {"notification_email": "me@example.org",
                                                 "smtp_server": "smtp.example.org"}
        # The saved, shared model artifact still carries no address.
        from JBGProjectStorage import project_csv_storage
        repository, scope = project_csv_storage(project, root=tmp_path / "csv")
        with repository.open_artifact(scope, spec["csv"]["configuration_id"]) as stream:
            saved = stream.read().decode("utf-8")
        assert '"notification_email"' in saved and "me@example.org" not in saved


def test_the_worker_check_allows_the_address_but_not_sql_identity():
    from JBGRunConfigurationValidators import CSVRunConfigurationValidator
    import inspect
    source = inspect.getsource(CSVRunConfigurationValidator)
    assert "configuration.mail.notification_email" not in source
    assert "conn.sql_username or conn.sql_password" in source
