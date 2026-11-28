"""301r (asked 2026-11-27): one Export button per view, only where the view has
a table with rows, in the format chosen under a new Settings tab at the right
end of the navigation, after About. Settings holds Language and Export format
(Excel or CSV); the language switch moved there from the masthead."""
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from test_revision_288a_project_runs import _client, _setup  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def test_the_settings_tab(tmp_path):
    with _client(tmp_path) as client:
        page = client.get("/ui/settings").text
        nav = page.split('<nav class="tabs"')[1].split("</nav>")[0]
        saved = client.post("/ui/settings", data={"language": "en", "export_format": "csv"},
                            follow_redirects=False)
        after = client.get(saved.headers["location"]).text
        bad = client.post("/ui/settings", data={"language": "fi", "export_format": "pdf"},
                          follow_redirects=False)
    assert nav.rstrip().endswith('aria-current="page">Inställningar</a>')
    assert 'class="on right"' in nav
    assert 'name="language" value="sv" checked' in page and 'name="export_format" value="xlsx" checked' in page
    assert 'action="/ui/language"' not in page                       # not in the masthead any more
    assert "jbg_lang=en" in saved.headers.get("set-cookie", "")
    assert "jbg_export=csv" in saved.headers.get("set-cookie", "")
    assert "The settings are saved." in after                          # now in English
    assert 'name="export_format" value="csv" checked' in after
    assert "set-cookie" not in bad.headers                            # unknown values ignored


def test_one_export_button_in_the_chosen_format(tmp_path):
    with _client(tmp_path) as client:
        empty = client.get("/ui/projects").text                     # no project, no rows
        project, dataset, configuration = _setup(client)
        client.post(f"/ui/projects/{project}/open")
        excel = client.get(f"/ui/dataset?dataset={dataset}&view=profile").text
        client.post("/ui/settings", data={"export_format": "csv"})
        csv = client.get(f"/ui/dataset?dataset={dataset}&view=profile").text
        about = client.get("/ui/about").text
        settings = client.get("/ui/settings").text
    assert "Exportera (" not in empty
    assert excel.count("Exportera (Excel)") == 1 and "export=xlsx" in excel
    assert csv.count("Exportera (CSV)") == 1 and "export=csv" in csv
    assert "Exportera (" not in about and "Exportera (" not in settings


def test_the_guides():
    for name, heading, sentence in (
            ("user_guide.sv.md", "\n## Inställningar\n", "Språket väljs under fliken Inställningar"),
            ("user_guide.en.md", "\n## Settings\n", "Choose the language under the Settings tab")):
        text = (ROOT / "docs" / name).read_text(encoding="utf-8")
        assert heading in text and sentence in text and "SV/EN" not in text
