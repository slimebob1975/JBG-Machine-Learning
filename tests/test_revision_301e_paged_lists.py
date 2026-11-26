"""301e (asked 2026-11-24): the Models list gets at least a third of the width,
and the long lists in the left panels (Models, Results, Run, Configuration,
Dataset) show seven rows at a time, Run History ten, the latest first, with
Previous and Next at the bottom right. The paging is done by jbg.js; without
it every row shows."""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "src" / "web" / "templates"
PAGED = {"models.html": 7, "results.html": 7, "run.html": 7, "configuration.html": 7,
         "dataset.html": 7, "history.html": 10}


@pytest.mark.parametrize("name,size", sorted(PAGED.items()))
def test_the_left_list_is_paged(name, size):
    text = (TEMPLATES / name).read_text(encoding="utf-8")
    tables = re.findall(r'<table class="grid" data-pager="(\d+)"', text)
    assert tables == [str(size)]                                   # only the list table
    start = text.index('data-pager="')
    body = text[start:text.index("</table>", start)]
    assert "class=\"{{ 'hl' if" in body                            # the list with the selection
    assert "data-pager-previous=\"{{ _('Previous') }}\"" in body


def test_the_models_list_is_wider():
    assert '<div class="layout-two run-layout models-layout">' in \
        (TEMPLATES / "models.html").read_text(encoding="utf-8")
    css = (ROOT / "src" / "web" / "static" / "jbg.css").read_text(encoding="utf-8")
    assert "div.layout-two.run-layout.models-layout { grid-template-columns: minmax(320px, 1fr) minmax(0, 2fr); }" in css


def test_the_script_pages_from_the_selected_row():
    script = (ROOT / "src" / "web" / "static" / "jbg.js").read_text(encoding="utf-8")
    assert 'document.querySelectorAll("table[data-pager]").forEach(wirePager);' in script
    assert 'var page = marked >= 0 ? Math.floor(marked / size) : 0;' in script
    assert "if (rows.length <= size) { return; }" in script


def test_a_page_renders_the_pager_attributes_in_swedish(tmp_path):
    pytest.importorskip("fastapi")
    from test_revision_288a_project_runs import _client, _setup
    with _client(tmp_path) as client:
        project, _, configuration = _setup(client)
        client.post(f"/ui/projects/{project}/open")
        page = client.get("/ui/configuration").text
    assert 'data-pager="7" data-pager-previous="Föregående" data-pager-next="Nästa" data-pager-of="av"' in page


def test_the_guides():
    sv = (ROOT / "docs" / "user_guide.sv.md").read_text(encoding="utf-8")
    en = (ROOT / "docs" / "user_guide.en.md").read_text(encoding="utf-8")
    assert "visar sju rader åt gången (Körhistorik tio)" in " ".join(sv.split())
    assert "show seven rows at a time (Run History ten)" in " ".join(en.split())
    # 300x missed the masthead's name here, split over two lines.
    for text in (sv, en):
        assert not re.search(r"JBG\s+Automati", text)
        assert "”JBG Machine Learning”" in text or '"JBG Machine Learning"' in text
