"""301f (asked 2026-11-24): the dataset picture gets a point-size slider, and
every class value, a missing class included, its own shape when the shape
shows the class (before, "no class" shared the first class's circle)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = (ROOT / "src" / "web" / "static" / "jbg.js").read_text(encoding="utf-8")


def test_no_class_has_a_shape_of_its_own():
    assert 'var index = name === null ? data.classes.length : classIndex[name];' in SCRIPT
    assert 'if (byCluster) { return classShape(p["class"]); }' in SCRIPT
    assert '"circle" : VIZ_SHAPES[classIndex' not in SCRIPT
    assert '"pentagon", "hexagon"]' in SCRIPT


def test_the_point_size_redraws_without_recomputing():
    assert 'if (sizer) { sizer.addEventListener("input", draw); }' in SCRIPT
    assert "pointSize(), code.colour(p)" in SCRIPT
    page = (ROOT / "src" / "web" / "templates" / "dataset.html").read_text(encoding="utf-8")
    assert 'min="1.5" max="10" step="0.5" value="4" data-viz-size' in page
    assert ' name=' not in page[page.index('<input type="range" min="1.5"'):page.index("data-viz-size")]


def test_the_texts():
    from JBGWebUI import _load_catalog
    assert _load_catalog("sv")["Point size"] == "Punktstorlek"
    sv = " ".join((ROOT / "docs" / "user_guide.sv.md").read_text(encoding="utf-8").split())
    assert "Varje klassvärde, även saknad klass, får en egen form." in sv
    assert "**Punktstorlek** gör punkterna större eller mindre." in sv
