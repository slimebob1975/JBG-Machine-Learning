"""300p (asked 2026-11-20): configurations count versions from 0 (the first
change makes version 1); the configuration list shows the last created or
changed first; the Results tab's run list shows the dataset as the Training
tab does; the Dark Numbers confusion matrices are drawn one per estimate,
like the Overview's."""
import time

from JBGIdentity import AuthenticatedPrincipal, AuthenticationMode
from test_revision_288a_project_runs import _client, _setup

OWNER = AuthenticatedPrincipal(AuthenticationMode.LOCAL, "developer").principal_key


def test_versions_from_zero_and_the_count_of_versions(tmp_path):
    with _client(tmp_path) as client:
        project, dataset, configuration = _setup(client)
        url = f"/api/projects/{project}/configurations/{configuration}"
        assert client.get(url).json()["version"] == 0
        saved = client.put(url, json={"settings": {"debug": {"data_limit": 5}},
                                      "expected_version": 0})
        assert saved.status_code == 200 and saved.json()["version"] == 1
        repository = client.app.state.jbg["configuration_service"]._repository
        assert repository.revision_count(OWNER, project, configuration) == 2
        client.post(f"/ui/projects/{project}/open")
        page = client.get(f"/ui/configuration/{configuration}/delete").text
        assert "Konfigurationen med alla sina versioner: 2" in page


def test_the_last_changed_configuration_comes_first(tmp_path):
    with _client(tmp_path) as client:
        project, dataset, first = _setup(client)
        time.sleep(0.02)
        second = client.post(f"/api/projects/{project}/configurations",
                             json={"name": "Andra"}).json()["configuration_id"]
        names = lambda: [c["name"] for c in
                         client.get(f"/api/projects/{project}/configurations").json()]
        assert names()[0] == "Andra"
        time.sleep(0.02)
        client.put(f"/api/projects/{project}/configurations/{first}",
                   json={"settings": {"debug": {"data_limit": 5}}, "expected_version": 0})
        assert names()[0] != "Andra"


def test_the_results_list_names_the_dataset(tmp_path):
    from JBGApplicationContracts import DataSourceKind, RunStatus
    with _client(tmp_path) as client:
        project, dataset, configuration = _setup(client)
        client.post(f"/ui/projects/{project}/open")
        store = client.app.state.jbg["store"]
        run = store.create(OWNER, DataSourceKind.CSV, {"spec_version": 1, "project_run": {
            "project_id": project, "kind": "training", "dataset_id": dataset,
            "configuration_name": "Standard", "configuration_version": 0}})
        store.claim(run, "w")
        store.finish(run, "w", RunStatus.SUCCEEDED, result={"schema_version": 1})
        page = client.get("/ui/results").text
        name = next(d["name"] for d in client.get(f"/api/projects/{project}/datasets").json())
        assert "<th>Dataset / Konfiguration</th>" in page
        assert f'<b>{name}</b><br><span class="muted">Standard v0</span>' in page


def test_the_dark_matrices_are_drawn_per_estimate():
    from JBGWebUI import WEB
    from JBGWebUIResults import dark_matrices
    detail = {"columns": ["Model type", "", "a", "b"],
              "rows": [["Korstränad modell, testdata", "a", 9, 1], ["", "b", 2, 8],
                       ["Slutlig modell, alla data", "a", 40, 5], ["", "b", 3, 52]]}
    matrices = dark_matrices(detail)
    assert [m["estimate"] for m in matrices] == ["Korstränad modell, testdata",
                                                 "Slutlig modell, alla data"]
    assert matrices[1]["rows"][1] == {"actual": "b", "values": [3, 52]}
    template = (WEB / "templates" / "results.html").read_text(encoding="utf-8")
    block = template.split("{% for m in dark_matrices %}")[1].split("{% endfor %}\n        </div>")[0]
    assert 'class="grid matrix"' in block and "' diag' if m.classes[loop.index0] == r.actual" in block
