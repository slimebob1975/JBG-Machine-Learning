"""301s (asked 2026-11-27): only data, configuration settings and results are
exported, not the lists of the left panels; the Export button stands below the
tables, on the right, in the right-hand card."""
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from JBGWebUIExport import EXPORTERS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "src" / "web" / "templates"


def test_no_list_of_a_left_panel_is_exported():
    assert "projects.html" not in EXPORTERS and "overview.html" not in EXPORTERS
    source = (ROOT / "src" / "JBGWebUIExport.py").read_text(encoding="utf-8")
    for listed in ('_("Datasets")', '_("Runs")', '_("Models"), context.get("models")',
                   '_("Configurations")', '_("Prediction runs")', '_("Latest runs")'):
        assert listed not in source, listed


@pytest.mark.parametrize("name", ["dataset", "run", "models", "prediction", "history",
                                  "configuration", "results"])
def test_the_button_ends_the_right_hand_card(name):
    text = (TEMPLATES / f"{name}.html").read_text(encoding="utf-8")
    assert text.count('{% include "_export.html" %}') == 1
    include = text.index('{% include "_export.html" %}')
    assert text.index("</aside>") > include > text.index("<aside")
    assert text[include:text.index("</aside>")].count("\n") == 1     # right before it closes


def test_on_the_pages(tmp_path):
    from test_revision_288a_project_runs import _client
    from test_revision_301c_run_history import _two_versions
    with _client(tmp_path) as client:
        project, dataset, configuration, first, second = _two_versions(client)
        pages = {"projects": client.get("/ui/projects").text,
                 "overview": client.get("/ui/overview").text,
                 "profile": client.get(f"/ui/dataset?dataset={dataset}&view=profile").text,
                 "history": client.get(f"/ui/history?compare={first}&compare={second}").text}
    assert 'class="export-links"' not in pages["projects"] + pages["overview"]
    for name in ("profile", "history"):
        aside = pages[name][pages[name].index("<aside"):pages[name].index("</aside>")]
        assert aside.rfind("</table>") < aside.index('class="export-links"'), name
    css = (ROOT / "src" / "web" / "static" / "jbg.css").read_text(encoding="utf-8")
    assert ".export-links { display: flex; gap: 8px; justify-content: flex-end;" in css
