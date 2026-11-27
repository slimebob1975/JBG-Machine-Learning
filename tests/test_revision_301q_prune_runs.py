"""301q (decided 2026-11-26): gallring of runs per project. A run goes only if
it is neither among the latest N runs nor younger than M days, and goes
entirely, its entry in Run History too, only when the user chooses "Gallra nu"
after a preview. Runs that trained a model in the catalog stay, as do queued
and running runs."""
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from sqlalchemy import update  # noqa: E402

from JBGApplicationContracts import DataSourceKind, RunReference, RunStatus  # noqa: E402
from JBGIdentity import AuthenticatedPrincipal, AuthenticationMode  # noqa: E402
from test_revision_288a_project_runs import _client, _setup  # noqa: E402

OWNER = AuthenticatedPrincipal(AuthenticationMode.LOCAL, "developer").principal_key
ROOT = Path(__file__).resolve().parent.parent
AGES = [1, 5, 40, 50, 60, 70, 80]                 # days; the oldest is still running


def _runs(client, project, dataset, configuration):
    store = client.app.state.jbg["store"]
    now = datetime.now(timezone.utc)
    made = {}
    for days in AGES:
        key = store.create(OWNER, DataSourceKind.CSV, {"spec_version": 1, "project_run": {
            "project_id": project, "kind": "training", "configuration_id": configuration,
            "configuration_version": 0, "dataset_id": dataset}}).key
        if days != 80:
            store.claim(RunReference(key), "w")
            store.finish(RunReference(key), "w", RunStatus.SUCCEEDED, result={"schema_version": 1})
        with store._engine.begin() as connection:
            connection.execute(update(store._jobs).where(store._jobs.c.run_id == key)
                               .values(created_at=now - timedelta(days=days)))
        made[days] = key
    client.app.state.jbg["models"].register(OWNER, project, "Modell", str(uuid.uuid4()),
                                            dataset_id=dataset, run_id=made[60])
    return store, made


def test_a_run_goes_only_when_it_breaks_both_rules(tmp_path):
    with _client(tmp_path) as client:
        project, dataset, configuration = _setup(client)
        client.post(f"/ui/projects/{project}/open")
        store, made = _runs(client, project, dataset, configuration)
        plan = client.app.state.jbg["deletion"].plan_prune(OWNER, project, 3, 30)
        assert sorted(r.run.key for r in plan.runs) == sorted([made[50], made[70]])
        assert (plan.kept_for_models, plan.kept_busy) == (1, 1)
        everything = client.app.state.jbg["deletion"].plan_prune(OWNER, project, 0, 0)
        assert len(everything.runs) == 5                     # all but the model's and the running
        none = client.app.state.jbg["deletion"].plan_prune(OWNER, project, 10, 0)
        assert none.runs == []                               # all are among the latest 10
        with pytest.raises(ValueError):
            client.app.state.jbg["deletion"].plan_prune(OWNER, project, -1, 3)


def test_the_preview_and_prune_now(tmp_path):
    with _client(tmp_path) as client:
        project, dataset, configuration = _setup(client)
        client.post(f"/ui/projects/{project}/open")
        store, made = _runs(client, project, dataset, configuration)
        panel = client.get(f"/ui/projects?selected={project}").text
        preview = client.get("/ui/projects/prune", params={"keep_latest": 3, "keep_days": 30}).text
        before = {r.run.key for r in store.list_for_owner(OWNER, None)}
        done = client.post("/ui/projects/prune", data={"keep_latest": 3, "keep_days": 30},
                           follow_redirects=False)
        after = {r.run.key for r in store.list_for_owner(OWNER, None)}
        message = client.get(done.headers["location"]).text
        again = client.get("/ui/projects/prune", params={"keep_latest": 3, "keep_days": 30}).text
    assert "Gallra körningar" in panel and 'action="/ui/projects/prune"' in panel
    assert "Behålls: de senaste <b>3</b> körningarna" in preview
    assert re.search(r"Gallra nu: 2", preview)
    assert "modellen behöver dem): 1" in preview and "köade eller pågår: 1" in preview
    assert before - after == {made[50], made[70]}           # nothing else, and the records too
    assert "Körningarna är gallrade." in message
    assert "Ingenting: ingen körning bryter mot båda reglerna." in again
    assert "disabled>Gallra nu" in again


def test_the_guides():
    sv = " ".join((ROOT / "docs" / "user_guide.sv.md").read_text(encoding="utf-8").split())
    assert "**Gallra körningar** finns för det öppna projektet." in sv
