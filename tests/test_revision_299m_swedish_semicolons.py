"""299m (asked 2026-11-13): Swedish instructions to the user use an ordinary
comma, a dash or two sentences instead of a semicolon. The one exception
(agreed 2026-11-13): the list of alphas in the Dark Numbers calculation table
keeps its semicolons, as the comma is the decimal sign there (299f2)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _messages():
    lines = (ROOT / "src" / "web" / "i18n" / "sv.po").read_text(encoding="utf-8").splitlines()
    texts, current = [], None
    for line in lines:
        if line.startswith("msgstr "):
            current = [line[len("msgstr "):]]
            texts.append(current)
        elif line.startswith('"') and current is not None:
            current.append(line)
        else:
            current = None
    return ["".join(part.strip('"') for part in text) for text in texts]


def test_no_swedish_message_has_a_semicolon():
    found = [text for text in _messages() if ";" in text and "charset=" not in text]
    assert found == []


def test_the_swedish_guide_has_no_semicolon():
    guide = (ROOT / "docs" / "user_guide.sv.md").read_text(encoding="utf-8")
    assert [line for line in guide.splitlines() if ";" in line] == []


def test_the_alpha_list_keeps_its_semicolons():
    from JBGWebUIResults import alpha_text
    assert alpha_text("[1, np.float64(0.7205267055383298)]", "sv") == "1; 0,7205"
