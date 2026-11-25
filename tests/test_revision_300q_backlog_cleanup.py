"""300q (asked 2026-11-23): BACKLOG.md lists open work only, checked against the
code and the CHANGELOG. The 300p BACKLOG is kept unchanged in
docs/backlog_archive_300p.md, and the new file records what was closed."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKLOG = (ROOT / "BACKLOG.md").read_text(encoding="utf-8")
ARCHIVE_PATH = ROOT / "docs" / "backlog_archive_300p.md"


def test_the_sections():
    headings = [line for line in BACKLOG.splitlines() if line.startswith("#")]
    assert headings[0].startswith("# JBG Machine Learning - Active BACKLOG")      # 300x
    for heading in ("## Current priorities", "### Now: stabilisation", "### Pending decision",
                    "### Deferred: future development", "## Standing rules",
                    "## Closed in the 300q cleanup"):
        assert any(h.startswith(heading) for h in headings), heading


def test_the_archive_keeps_the_300p_backlog():
    archive = ARCHIVE_PATH.read_text(encoding="utf-8")
    assert archive.startswith("# BACKLOG archive: the BACKLOG as it stood at revision 300p\n")
    assert "Nothing below is an active priority" in archive
    kept = archive.split("\n---\n\n", 1)[1]
    assert kept.startswith("# JBG AutoClassification - Active BACKLOG (revision 272)\n")
    assert "- [x] 300p (2026-11-20)" in kept
    assert "Release commit: 51d19c17a6e3f03ca20127b71056338d63f934ce" in kept
    assert "`docs/backlog_archive_300p.md`" in BACKLOG


def test_the_backlog_names_only_existing_files():
    # Paths in backticks must exist, except patterns and the one file the
    # BACKLOG itself says is gone.
    gone = {"docs/backlog_archive_pre_152.md"}
    for path in re.findall(r"`([^`\s]+)`", BACKLOG):
        if "/" not in path and not re.search(r"\.(md|py|ps1|txt)$", path):
            continue
        if any(c in path for c in "*<{") or path.startswith(("GET", "/")) or path in gone:
            continue
        candidates = [ROOT / path, ROOT / "src" / path, ROOT / "docs" / "dark_numbers" / path]
        assert any(c.exists() for c in candidates), path


def test_the_interim_catalog_is_not_used_by_the_web_interface():
    # The BACKLOG's reason why the catalog can go: only the API serves it.
    web = ROOT / "src" / "web"
    users = [p for p in web.rglob("*") if p.suffix in {".html", ".js"}
             and "/api/configurations" in p.read_text(encoding="utf-8")]
    users += [p for p in (ROOT / "src").glob("JBGWebUI*.py")
              if "JBGSavedConfigurations" in p.read_text(encoding="utf-8")]
    assert users == []


def test_the_swedish_rules_stay():
    assert "semicolon" in BACKLOG and "299f2" in BACKLOG          # 299h's test
    assert '"osedd del"' in BACKLOG


def test_text_files_end_with_one_newline():
    for path in (ROOT / "BACKLOG.md", ARCHIVE_PATH):
        text = path.read_text(encoding="utf-8")
        assert text.endswith("\n") and not text.endswith("\n\n"), path
