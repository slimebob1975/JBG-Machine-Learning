"""300x (decided 2026-11-24): the product is called JBG Machine Learning, in
English in the masthead in both languages. The saved-model format identifier
keeps the earlier name, since loading checks it."""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_the_name_in_the_code_and_the_documents():
    from JBGVersion import APP_NAME, BuildIdentity
    assert APP_NAME == "JBG Machine Learning" and BuildIdentity().app_name == APP_NAME
    for path, heading in (("README.md", "# JBG Machine Learning\n"),
                          ("BACKLOG.md", "# JBG Machine Learning - Active BACKLOG\n"),
                          ("docs/user_guide.sv.md", "# JBG Machine Learning\n"),
                          ("docs/user_guide.en.md", "# JBG Machine Learning\n"),
                          ("docs/gui/JBG_web_gui_design.md", "# JBG Machine Learning – Web GUI")):
        assert (ROOT / path).read_text(encoding="utf-8").startswith(heading), path
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "& .\\scripts\\start_fastapi_local.ps1 -Port 8000" in readme
    for path in ("src/JBGLogger.py", "src/JBGStreamedLogger.py"):
        source = (ROOT / path).read_text(encoding="utf-8")
        assert "WELCOME TO JBG MACHINE LEARNING" in source and "AUTOMATIC CLASSIFICATION" not in source


def test_saved_models_keep_their_format_identifier():
    from JBGModelPersistence import MODEL_ARTIFACT_FORMAT
    assert MODEL_ARTIFACT_FORMAT == "JBGAutoClassification.model"


@pytest.mark.parametrize("language", ["sv", "en"])
def test_the_masthead_is_english_in_both_languages(tmp_path, language):
    pytest.importorskip("fastapi")
    from test_revision_300r_rename import _client
    with _client(tmp_path) as client:
        client.post("/ui/language", data={"language": language, "back": "/ui/projects"},
                    follow_redirects=False)
        page = client.get("/ui/projects").text
    assert "<h1>Machine Learning</h1>" in page
    assert "Automatisk klassificering" not in page and "Automatic classification" not in page


def test_the_old_swedish_name_is_gone_from_the_catalogue():
    po = (ROOT / "src" / "web" / "i18n" / "sv.po").read_text(encoding="utf-8")
    assert "Automatisk klassificering" not in po
