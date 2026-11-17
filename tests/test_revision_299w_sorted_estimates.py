"""299w (settled 2026-11-16, DN-01 F9): the four Dark Number estimates are
model variants forming an interval with subintervals. They are shown sorted
from the lowest to the highest (undefined last), each labelled with its model
variant, and there is no order check (after 299u, c corrects the in-sample
variants, so no order follows from the method)."""
from JBGWebUIResults import with_growth, with_percentages
from test_revision_299v_dark_number_growth import DETAIL
from JBGWebUIResults import matrix_counts


def _summary():
    return [{"target": "dog", "formula": "separated_alpha", "status": "broken",
             "points": [{"label": "D_re_full", "value": 0.03},
                        {"label": "D_cv_full", "value": None, "reason": "undefined rate"},
                        {"label": "D_comb", "value": 0.01},
                        {"label": "D_cv_test", "value": 0.02}]}]


def test_the_estimates_are_sorted_with_undefined_last():
    summary = with_percentages(_summary(), "sv")
    assert [p["label"] for p in summary[0]["points"]] == \
        ["D_comb", "D_cv_test", "D_re_full", "D_cv_full"]
    assert summary[0]["range_text"] == "1,00 % – 3,00 %"


def test_the_growth_view_sorts_by_growth():
    summary = with_growth(with_percentages(_summary(), "sv"), matrix_counts(DETAIL), "sv")
    labels = [p["label"] for p in summary[0]["growth_points"]]
    growths = [p["growth"] for p in summary[0]["growth_points"] if p["growth"] is not None]
    assert growths == sorted(growths) and labels[-1] in ("D_re_full", "D_cv_full")


def test_no_order_check_and_subintervals_shown():
    import re
    from JBGWebUI import WEB, _load_catalog
    template = (WEB / "templates" / "results.html").read_text(encoding="utf-8")
    assert "expected order" not in template and "could not be checked" not in template
    assert template.count('{{ _("Subintervals") }}') == 2
    catalog = _load_catalog("sv")
    dark = template.split('{% if view == "dark_numbers" %}')[1].split("{% else %}\n          <p class=\"hint\">{{ _(\"No summary")[0]
    for text in re.findall(r'_\("([^"]+)"\)', dark):
        assert text in catalog, text
