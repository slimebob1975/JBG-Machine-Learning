"""301u (asked 2026-11-27): the dataset picture saved as a PNG, with a title
(dataset, method, rows) above and the legend below, at double resolution,
made in the browser (no server part)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = (ROOT / "src" / "web" / "static" / "jbg.js").read_text(encoding="utf-8")


def test_the_button_follows_the_picture():
    page = (ROOT / "src" / "web" / "templates" / "dataset.html").read_text(encoding="utf-8")
    assert 'data-viz-png hidden' in page and 'data-dataset="{{ selected.name }}"' in page
    assert '{{ _("Save as PNG") }}' in page
    assert 'if (shown) { shown.hidden = false; }' in SCRIPT                 # after drawing
    assert 'if (hide) { hide.hidden = true; }' in SCRIPT                    # on a refusal


def test_the_image_has_title_legend_and_styles_written_in():
    assert "function vizImageSvg(plot, legend, title)" in SCRIPT
    assert '"viz-boundary": { fill: "none", stroke: "#33404d"' in SCRIPT
    assert '<rect width="100%" height="100%" fill="#ffffff"/>' in SCRIPT
    assert "var scale = 2, canvas = document.createElement(\"canvas\");" in SCRIPT
    assert 'canvas.toBlob(function (blob) {' in SCRIPT and '"image/png"' in SCRIPT


def test_the_texts():
    from JBGWebUI import _load_catalog
    assert _load_catalog("sv")["Save as PNG"] == "Spara som PNG"
    sv = " ".join((ROOT / "docs" / "user_guide.sv.md").read_text(encoding="utf-8").split())
    assert "**Spara som PNG** under bilden" in sv
