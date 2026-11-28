"""301l (asked 2026-11-26): version 0.20.1, the release of the web GUI."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_the_version():
    from JBGVersion import APP_VERSION, BuildIdentity
    assert APP_VERSION == "0.20.2" and BuildIdentity().app_version == "0.20.2"   # 301v


def test_the_changelog_has_the_release():
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert changelog.index("## Version 0.20.1") < changelog.index("## Version 0.19.1")


def test_saved_models_keep_their_format():
    from JBGModelPersistence import MODEL_ARTIFACT_FORMAT
    assert MODEL_ARTIFACT_FORMAT == "JBGAutoClassification.model"


def test_the_masthead_shows_it(tmp_path):
    import pytest
    pytest.importorskip("fastapi")
    from test_revision_288a_project_runs import _client
    with _client(tmp_path) as client:
        page = client.get("/ui/projects").text
    assert "v0.20.2" in page                                  # 301v
