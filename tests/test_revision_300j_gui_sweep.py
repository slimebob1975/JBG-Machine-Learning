"""300j (agreed 2026-11-19): a systematic sweep of the web GUI after a real
training run (Dark Numbers on), a model and a feature investigation: every tab
and view, in Swedish and English, with and without an open project. A page may
not give a server error, a Swedish page may not show an untranslated text from
the catalogue, and no internal link may lead nowhere."""
import time
from datetime import timedelta

from fastapi.testclient import TestClient

import test_revision_281c_csv_application_e2e as revision_281c
from gui_sweep import browser_sweep, sweep


class GuiSweepNative300j(revision_281c.CSVApplicationEndToEnd281c):
    test_registered_csv_trains_and_reloads_model_through_application = None
    test_other_scope_cannot_prepare_csv_run = None

    def test_every_page_and_view(self):
        from JBGFastAPIServer import create_server_app
        from JBGMetadataStore import MetadataStoreSettings
        self._configure_training()
        self.config.mail.notification_email = ""
        with self.repo.open_artifact(self.scope, self.ref.artifact_id) as stream:
            data = stream.read()
        work = self.root / "api"
        work.mkdir()
        client = TestClient(create_server_app(
            settings=MetadataStoreSettings(sqlite_path=work / "jobs.sqlite"),
            run_logs=work / "run-logs", csv_root=work / "csv", model_root=work / "models",
            results_root=work / "runs",
            dispatcher_options={"script_path": self.root, "heartbeat_seconds": 5,
                                "stale_after": timedelta(minutes=10), "poll_seconds": 1}))
        with client:
            try:
                self.findings = self._sweep(client, work, data)
            finally:
                from test_revision_296b_csv_predictions import _wait_for_workers_to_exit
                _wait_for_workers_to_exit(client)
        print("\nSWEEP FINDINGS:\n" + "\n".join(self.findings))
        self.assertEqual(self.findings, [])

    def _sweep(self, client, work, data):
        from test_revision_288a_project_runs import _setup
        from test_revision_296b_csv_predictions import CSVPredictionNative296b
        empty = sweep(client, ["/ui", "/ui/overview", "/ui/projects", "/ui/dataset",
                               "/ui/configuration", "/ui/run", "/ui/results", "/ui/models",
                               "/ui/prediction", "/ui/about"])
        settings = self.config._config_to_json(username="")
        settings["mode"].update(predict=False, calculate_dark_numbers=True,
                                feature_search_preset="Custom", feature_search_trials=2,
                                feature_search_sizes=[2], feature_search_inner_folds=2,
                                feature_search_outer_folds=2, feature_search_top_sets=1,
                                feature_search_refine_rounds=0,
                                feature_search_max_evaluations=3)
        project, dataset, configuration = _setup(client, data=data, roles=settings)
        client.post(f"/ui/projects/{project}/open", follow_redirects=False)
        client.post(f"/ui/configuration/{configuration}/select", follow_redirects=False)
        run = client.post(f"/api/projects/{project}/runs",
                          json={"configuration_id": configuration}).json()["run_id"]
        CSVPredictionNative296b._wait(self, client, run, work)
        deadline, models = time.time() + 30, []
        while time.time() < deadline and not models:
            models = client.get(f"/api/projects/{project}/models").json()
            time.sleep(0.3)
        model = models[0]["model_id"]
        client.post(f"/ui/models/{model}/choose", follow_redirects=False)
        started = client.post("/ui/run/investigate", follow_redirects=False)
        investigation = started.headers["location"].split("run=")[1].split("&")[0]
        CSVPredictionNative296b._wait(self, client, investigation, work)
        pages = ["/ui", "/ui/overview", "/ui/projects", f"/ui/projects?selected={project}",
                 f"/ui/projects/{project}/delete",
                 f"/ui/dataset?dataset={dataset}",
                 *[f"/ui/dataset?dataset={dataset}&view={v}"
                   for v in ("preview", "profile", "classes", "roles")],
                 f"/ui/dataset/{dataset}/delete",
                 f"/ui/configuration?configuration={configuration}",
                 f"/ui/configuration/{configuration}/delete",
                 "/ui/run", f"/ui/run?run={run}", f"/ui/run?run={investigation}",
                 f"/ui/runs/{run}/log", f"/ui/runs/{run}/delete",
                 "/ui/results", f"/ui/results?run={run}",
                 *[f"/ui/results?run={run}&view={v}" for v in
                   ("overview", "leaderboard", "mispredictions", "feature_importance",
                    "dark_numbers")],
                 f"/ui/results?run={run}&view=dark_numbers&dark_view=growth",
                 f"/ui/results?run={investigation}",
                 "/ui/models", f"/ui/models?model={model}", f"/ui/models/{model}/delete",
                 "/ui/prediction", "/ui/about"]
        cookies = {name: value for name, value in client.cookies.items()}
        return [f"(no project) {f}" for f in empty] + sweep(client, pages) \
            + browser_sweep(client.app, pages, cookies)


def test_every_text_sent_for_translation_is_in_the_catalogue():
    """Static: the templates' _("...") texts and the label tables shown in the
    GUI all have a Swedish translation (a missing one would show in English)."""
    import re
    import JBGConfigSchema
    import JBGWebUI
    import JBGWebUIDeletion
    import JBGWebUIPrediction
    import JBGWebUIResults
    import JBGWebUIRun
    catalog = JBGWebUI._load_catalog("sv")
    missing = []
    for template in sorted((JBGWebUI.WEB / "templates").glob("*.html")):
        source = template.read_text(encoding="utf-8")
        texts = re.findall(r'_\(\s*"((?:[^"\\]|\\.)*)"\s*\)', source) + \
            re.findall(r"_\(\s*'((?:[^'\\]|\\.)*)'\s*\)", source)
        missing += [f"{template.name}: {t}" for t in texts
                    if t.replace('\\"', '"').replace("\\'", "'") not in catalog]
    tables = {"MESSAGES": JBGWebUI.MESSAGES, "RUN": JBGWebUIRun.MESSAGES,
              "PREDICTION": JBGWebUIPrediction.MESSAGES, "REFUSALS": JBGWebUIDeletion.REFUSALS,
              "DARK_COLUMNS": JBGWebUIResults.DARK_COLUMNS,
              "DARK_REASONS": JBGWebUIResults.DARK_REASONS,
              "DARK_ESTIMATES": JBGWebUIResults.DARK_ESTIMATES,
              "OOF_QUALITY": JBGWebUIResults.OOF_QUALITY,
              "CORRECTION_SOURCES": JBGWebUIResults.CORRECTION_SOURCES,       # 300n
              "OPTION_LABELS": JBGConfigSchema.OPTION_LABELS}
    for name, table in tables.items():
        for value in table.values():
            text = value[1] if isinstance(value, tuple) else value
            if isinstance(text, str) and text not in catalog:
                missing.append(f"{name}: {text}")
    assert missing == []


def test_no_resource_is_loaded_from_outside_the_server():
    """The GUI loads nothing from other hosts (the font came from Google Fonts)."""
    import re
    from JBGWebUI import WEB
    found = []
    for path in list((WEB / "templates").glob("*.html")) + list((WEB / "static").glob("*.css")) \
            + list((WEB / "static").glob("*.js")):
        text = path.read_text(encoding="utf-8")
        for url in re.findall(r'(?:href|src)=["\'](https?://[^"\']+)|url\(["\']?(https?://[^)"\']+)',
                              text):
            found.append(f"{path.name}: {[u for u in url if u][0]}")
    assert found == []
    fonts = sorted(p.name for p in (WEB / "static" / "fonts").glob("*.woff2"))
    assert len(fonts) == 6 and (WEB / "static" / "fonts" / "OFL.txt").exists()
