"""299l (agreed 2026-11-16): the Algorithms section lists the algorithms in
groups (Linear, Non-linear, Neighbours and centroids, Naive Bayes, Trees, three
Ensemble groups, Imbalanced data, Robust to mislabelling, Neural networks,
Special), sorted by name within each group, each group with "select all" and
"clear". What is saved is unchanged."""
import re
from datetime import timedelta

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("jinja2")

from JBGConfigSchema import ALGORITHM_GROUPS, option_groups  # noqa: E402


def _schema(language="sv"):
    from JBGConfigSchema import configuration_schema
    from JBGConfigurationService import _server_template
    from JBGWebUI import translator
    return configuration_schema("csv", translator(language), _server_template())


def test_every_algorithm_has_exactly_one_group():
    import JBGMeta
    grouped = [code for _, codes in ALGORITHM_GROUPS for code in codes]
    assert len(grouped) == len(set(grouped))
    assert set(grouped) == {member.name for member in JBGMeta.Algorithm}


def test_groups_are_in_order_and_sorted_by_name():
    field = next(f for f in _schema()["fields"] if f["key"] == "mode.algorithm")
    groups = field["option_groups"]
    assert [g["label"] for g in groups] == [
        "Linjära", "Icke-linjära", "Grannar och centroider", "Naive Bayes", "Träd",
        "Ensemble: bagging och skogar", "Ensemble: boosting", "Ensemble: röstning och stapling",
        "Obalanserade data", "Robusta mot felmärkning", "Neurala nätverk", "Särskilda"]
    for group in groups:
        labels = [o["label"] for o in group["options"]]
        assert labels == sorted(labels, key=str.lower)
    assert sum(len(g["options"]) for g in groups) == len(field["options"])   # options unchanged
    linear = [o["value"] for o in groups[0]["options"]]
    assert linear == ["LDA", "LSVC", "LRN", "PAC", "PCN", "REC", "SGDE"]


def test_an_unknown_algorithm_goes_to_other():
    options = [{"value": "NEW", "label": "Brand new"}, {"value": "LRN", "label": "Logistic"}]
    groups = option_groups(options, ALGORITHM_GROUPS, lambda text: text)
    assert [(g["label"], [o["value"] for o in g["options"]]) for g in groups] == \
        [("Linear", ["LRN"]), ("Other", ["NEW"])]


def test_the_form_shows_the_groups_and_saves_as_before(tmp_path):
    from fastapi.testclient import TestClient
    from JBGFastAPIServer import create_server_app
    from JBGMetadataStore import MetadataStoreSettings
    from JBGSQLServer import SQLServerSettings
    with TestClient(create_server_app(
            settings=MetadataStoreSettings(sqlite_path=tmp_path / "jobs.sqlite"),
            run_logs=tmp_path / "run-logs", csv_root=tmp_path / "csv",
            model_root=tmp_path / "models", results_root=tmp_path / "runs",
            sql_server=SQLServerSettings(),
            dispatcher_options={"poll_seconds": 60, "heartbeat_seconds": 1,
                                "stale_after": timedelta(minutes=5)})) as client:
        location = client.post("/ui/projects", data={"name": "P", "source": "csv"},
                               follow_redirects=False).headers["location"]
        project = re.search(r"selected=([0-9a-f-]{36})", location).group(1)
        client.post(f"/ui/projects/{project}/open")
        configuration = client.post(f"/api/projects/{project}/configurations",
                                    json={"name": "C"}).json()["configuration_id"]
        page = client.get(f"/ui/configuration?configuration={configuration}").text
        section = page.split('name="f:mode.algorithm" value="ALL"')[1].split("</fieldset>")[0]
        heads = re.findall(r'<p class="choice-group-head"><b>([^<]+)</b>', section)
        assert heads[0] == "Linjära" and heads[-1] == "Särskilda" and len(heads) == 12
        assert section.count('data-group-set="1">välj alla</button>') == 12
        values = re.findall(r'name="f:mode.algorithm" value="([A-Z0-9]+)"', section)
        assert values[:3] == ["LDA", "LSVC", "LRN"] and len(values) == len(set(values))


def test_the_script_wires_the_groups():
    from JBGWebUI import WEB
    script = (WEB / "static" / "jbg.js").read_text(encoding="utf-8")
    assert "function wireChoiceGroup" in script and "forEach(wireChoiceGroup)" in script
