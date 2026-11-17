"""299u, JBG v1.2 (settled 2026-11-16, DN-01 F8 and the reading of the
equation): D estimates the hidden share H (of the rows registered as another
class, the share that really are the target class), so it is capped at 1 with
a flag. alpha_FN weighs the misses only: D = c a_FP (1 - TN_r)(1 + a_FN (1 - TP_r)).
c corrects in-sample estimates for memorisation and is not applied to the
unseen test part. Results -> Dark Numbers shows the equation with each part
explained, and the About tab (user guide) explains the method in detail."""
import pandas as pd
import pytest

from JBGDarkNumbers import DarkNumberCalculator as Calc

REAL = pd.Series([1, 1, 1, 1, 0, 0, 0, 0, 0, 0])
PRED = pd.Series([1, 1, 1, 0, 1, 1, 0, 0, 0, 0])            # TP 3, FN 1, FP 2, TN 4
PROB = pd.Series([0.9, 0.8, 0.7, 0.6, 0.7, 0.9, 0.8, 0.9, 0.6, 0.7])


def test_the_version():
    assert Calc.METHOD_VERSION == "1.2" and Calc.CAP == 1.0


def test_alpha_fn_weighs_the_misses_only():
    alphas, value = Calc().compute_dark_number_separated_alpha(REAL, PRED, PROB, 1.5)
    a_fp, a_fn = alphas
    assert (a_fp, a_fn) == (pytest.approx(0.8), pytest.approx(0.6))
    assert value == pytest.approx(1.5 * 0.8 * (2 / 6) * (1 + 0.6 * 0.25))
    # No misses: the scaling factor is 1, whatever alpha_FN would be.
    _, perfect = Calc().compute_dark_number_separated_alpha(
        REAL, pd.Series([1, 1, 1, 1, 1, 1, 0, 0, 0, 0]), PROB, 1.0)
    assert perfect == pytest.approx(0.8 * (2 / 6))


def test_d_is_capped_at_one_with_a_flag():
    real = pd.Series(["T", "T", "o", "o", "o"])
    pred = pd.Series(["o", "T", "T", "T", "T"])                # FPR 1, TPR 0.5
    rows = Calc().compute_dark_numbers(real, pred, pd.Series([0.9] * 5), type="all",
                                       corrs={"T": 4.0, "o": 1.0}, targets=["T"])
    assert set(rows["dark_number"]) == {1.0} and rows["capped"].all()
    fine = Calc().compute_dark_numbers(REAL.map({1: "T", 0: "o"}), PRED.map({1: "T", 0: "o"}),
                                       PROB, type="base", corrs={"T": 1.0}, targets=["T"])
    assert not fine["capped"].any() and fine["dark_number"].iloc[0] < 1


def test_the_formula_shown_is_the_one_computed():
    assert Calc.FORMULA_LATEX["separated_alpha"] == \
        r"D = c\,\alpha_{FP}\,(1 - TN_r)\,(1 + \alpha_{FN}\,(1 - TP_r))"


def test_the_summary_carries_the_cap_flag():
    from JBGDarkNumberReporting import build_dark_number_intervals
    rows = pd.DataFrame([{"Model type": "D_cv_full - M", "type": "separated_alpha", "target": "T",
                          "corr": 4.0, "corr_model": "M", "corr_source": "direct",
                          "dark_number": 1.0, "capped": True}])
    points = {p["label"]: p for p in build_dark_number_intervals(rows)[0]["points"]}
    assert points["D_cv_full"]["capped"] is True


@pytest.mark.parametrize("kind, symbols", [
    ("separated_alpha", ["D", "1 − TN<sub>r</sub>", "1 − TP<sub>r</sub>", "α<sub>FP</sub>",
                         "α<sub>FN</sub>", "c"]),
    ("base", ["D", "1 − TN<sub>r</sub>", "1 − TP<sub>r</sub>", "c"]),
    ("non_linear_alpha", ["D", "1 − TN<sub>r</sub>", "1 − TP<sub>r</sub>", "α", "k", "c"]),
])
def test_the_equation_section_explains_each_part(kind, symbols):
    from JBGWebUI import _load_catalog, translator
    from JBGWebUIResults import EQUATION_PARTS, dark_equation
    shown = dark_equation(kind, translator("sv"))
    assert [p["symbol"] for p in shown["parts"]] == symbols
    assert shown["card"]["mathml"].startswith("<math")
    catalog = _load_catalog("sv")
    assert all(text in catalog for _, text, _ in EQUATION_PARTS)


def test_the_results_template_and_the_guides():
    from pathlib import Path
    from JBGWebUI import WEB
    template = (WEB / "templates" / "results.html").read_text(encoding="utf-8")
    assert "{% if dark_equation %}" in template and 'selectattr("capped")' in template
    root = Path(__file__).resolve().parent.parent / "docs"
    english = (root / "user_guide.en.md").read_text(encoding="utf-8")
    swedish = (root / "user_guide.sv.md").read_text(encoding="utf-8")
    assert "### Dark Numbers in detail (JBG 1.2)" in english
    assert "### Mörkertal i detalj (JBG 1.2)" in swedish
    assert "`D = min(c · α_FP · (1 − TN_r) · (1 + α_FN · (1 − TP_r)), 1)`" in swedish
