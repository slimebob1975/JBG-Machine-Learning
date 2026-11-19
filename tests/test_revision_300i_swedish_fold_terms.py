"""300i (asked 2026-11-19): "veck"/"veckning" was a too literal translation of
"fold". The Dark Numbers area says "osedd del" (the part a model has not
seen), the flip test's progress "klara delar", the guide "4 delar och 2
upprepningar", and the feature investigation "inre/yttre delar"."""
import re
from pathlib import Path

from JBGWebUI import _load_catalog

ROOT = Path(__file__).resolve().parent.parent


def test_the_new_terms():
    catalog = _load_catalog("sv")
    assert catalog["Correction out-of-fold (c)"] == "Korrektion på osedd del (c)"
    assert catalog["c out-of-fold, lower (90 %)"] == "c på osedd del, nedre (90 %)"
    assert catalog["Quality of c out-of-fold"] == "Kvalitet för c på osedd del"
    assert catalog["Dark Number with c out-of-fold"] == "Mörkertal med c på osedd del"
    assert catalog["Accuracy on unseen rows"] == "Träffsäkerhet på osedd del"
    assert catalog["Correction factor: folds done"] == "Korrektionsfaktor: klara delar"
    assert catalog["outer folds"] == "yttre delar"


def test_no_fold_called_veck_in_swedish():
    words = re.compile(r"\bveck\b|\bvecks\b|veckning|\byttre veck|\binre veck", re.IGNORECASE)
    catalog = _load_catalog("sv")
    assert [t for t in catalog.values() if words.search(t)] == []
    guide = (ROOT / "docs" / "user_guide.sv.md").read_text(encoding="utf-8")
    assert not words.search(guide)
