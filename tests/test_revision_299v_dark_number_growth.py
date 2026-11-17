"""299v (asked 2026-11-16): Results -> Dark Numbers can show the Dark Number
as the growth of the target class. With D the hidden share among the rows
registered as another class (the cats that are really dogs), the hidden cases
are D * N_rest and the target class grows by g = D * N_rest / N_target, shown
as a percentage and a factor, with the counts behind it and the share of all
real target cases that were missing, g / (1 + g). A toggle chooses the view."""
import pytest

from JBGWebUIResults import matrix_counts, with_growth

DETAIL = {"columns": ["", "Model type", "dog", "cat"],
          "rows": [["dog", "D_cv_test - M", 8, 2], ["cat", "", 30, 960],
                   ["dog", "D_cv_full - M", 40, 10], ["cat", "", 150, 4800],
                   ["dog", "Combined (legacy full-data)", 45, 5], ["cat", "", 100, 4850]]}


def _summary(values):
    return [{"target": "dog", "formula": "separated_alpha",
             "points": [{"label": label, "value": value} for label, value in values.items()]}]


def test_the_counts_per_estimate_are_the_registered_rows():
    counts = matrix_counts(DETAIL)
    assert counts["D_cv_test - M"] == {"dog": 10.0, "cat": 990.0}
    assert counts["Combined (legacy full-data)"] == {"dog": 50.0, "cat": 4950.0}


def test_growth_percentage_factor_counts_and_missing_share():
    summary = with_growth(_summary({"D_cv_test": 0.02, "D_cv_full": 0.01}),
                          matrix_counts(DETAIL), "sv")
    test_part, full = summary[0]["points"]
    # 2 % of 990 cats are dogs: 19.8 hidden beside 10 registered dogs -> +198 %.
    assert test_part["growth"] == pytest.approx(1.98)
    assert test_part["growth_text"] == "+198,00 % (×2,98)"
    assert test_part["hidden"] == pytest.approx(19.8)
    assert test_part["registered_target"] == 10 and test_part["registered_rest"] == 990
    assert test_part["missing_text"] == "66,44 %"                  # 1.98 / 2.98
    assert full["growth"] == pytest.approx(0.01 * 4950 / 50)
    assert test_part["growth_bar"] == 100.0 and full["growth_bar"] == pytest.approx(50.0)
    assert summary[0]["growth_range_text"] == "+99,00 % – +198,00 %"


def test_english_and_missing_values():
    summary = with_growth(_summary({"D_cv_test": 0.02, "D_re_full": 0.5, "D_comb": None}),
                          matrix_counts(DETAIL), "en")
    points = {p["label"]: p for p in summary[0]["points"]}
    assert points["D_cv_test"]["growth_text"] == "+198.00 % (×2.98)"
    assert points["D_re_full"]["growth"] is None                    # no matrix for it
    assert points["D_comb"]["growth"] is None                       # undefined estimate


def test_no_registered_target_rows_gives_no_growth():
    detail = {"columns": ["", "Model type", "dog", "cat"],
              "rows": [["cat", "D_cv_test - M", 0, 10]]}
    summary = with_growth(_summary({"D_cv_test": 0.1}), matrix_counts(detail), "sv")
    assert summary[0]["points"][0]["growth"] is None


def test_the_template_offers_the_toggle_and_the_texts_are_translated():
    import re
    from JBGWebUI import WEB, _load_catalog
    template = (WEB / "templates" / "results.html").read_text(encoding="utf-8")
    assert "dark_view=growth" in template and "dark_view=share" in template
    block = template.split("299v: the growth of the target class follows")[1].split("{% endif %}")[0]
    catalog = _load_catalog("sv")
    for text in re.findall(r'_\("([^"]+)"\)', template.split("299v (asked 2026-11-16)")[1]
                           .split("{% for interval")[0]) + re.findall(r'_\("([^"]+)"\)', block):
        assert text in catalog, text
