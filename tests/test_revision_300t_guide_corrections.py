"""300t (found 2026-11-24): two passages in the user guides' Dark Numbers
section, found while building a presentation from the Om tab."""
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "docs"
SV = (DOCS / "user_guide.sv.md").read_text(encoding="utf-8")
EN = (DOCS / "user_guide.en.md").read_text(encoding="utf-8")


def test_what_comes_next_no_longer_promises_what_1_3_has():
    assert "Version 2 mäter" not in SV and "Version 2 measures" not in EN
    assert "finns sedan 1.3" in SV and "are in place since\n1.3" in EN
    assert "skattar den dolda andelen\ndirekt, med intervall" in SV
    assert "estimate the\nhidden share directly, with intervals" in EN


def test_the_flip_test_is_the_same_on_every_computer():
    assert "på alla datorer. Varje kopia" not in SV
    assert "Delarna är desamma på alla datorer,\n  oavsett antalet processorkärnor" in SV
    assert "on every computer. Each copy" not in EN
    assert "The parts are the same on every computer,\n  whatever its number of processor cores" in EN


def test_the_swedish_guide_keeps_its_rules():
    section = SV.split("### Mörkertal i detalj")[1].split("\n## ")[0]
    assert ";" not in section
    assert "veck" not in section.lower()
