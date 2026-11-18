# Validation of JBG 1.2 against a known truth – protocol

Status: **proposed 2026-11-16, to be approved before the study is run.** The
thresholds and decision rules below are fixed before any result is seen, so
that the method cannot be judged by numbers chosen afterwards. Agreed
2026-11-16: validate the current method first (a small version of DN-06),
then decide how much of the rest of the plan (DN-03 to DN-05) is needed.

Code: `src/JBGDarkNumberStudy.py` (outside the normal training flow).

## 1. What is measured

For a target class T, the Dark Number `D` estimates the hidden share
`H = P(Y = T | S ≠ T)`: of the rows registered as another class (S), the share
that really are T (Y). In synthetic data the true `H` is known. Each of the
four estimates is compared with the true `H` in its own part of the data:
the cross-trained model on the test part with the test part's `H`, the other
three with `H` over all data.

## 2. Synthetic populations

- 4 000 rows, six numeric features. True class T with probability `q` (the
  target share), otherwise R. T rows are shifted by `δ · (1, 0.6, 0.3, 0, 0, 0)`,
  with `δ` = 0.5 (weak), 1.0 (medium) or 2.0 (strong separation).
- Hiding: `h = round(H · N_R / (1 − H))` true T rows are registered as R, so
  that the share of T among the registered R is exactly `H`.
  - **one-sided** (the method's assumption): the hidden rows are drawn at
    random among the T rows;
  - **feature-dependent** (assumption broken): T rows with a lower first
    feature are hidden more often (weight `exp(−1.5 x₁)`);
  - **two-sided** (assumption broken): in addition, `h` true R rows are
    registered as T.
- Models, trained on the registered labels as in a real run: logistic
  regression and an MLP (32 hidden units), each after standard scaling.
  A random fifth of the rows is the test part; the cross-trained model is
  trained on the rest, the final model on all rows.
- The engine's own computation (`get_dark_numbers`) with the defaults of
  JBG 1.2: linear method, separated alpha, flip fraction 0.2, 4 folds × 2
  repeats, sampling as the pipeline, `1 ≤ c ≤ 10`, the cap at 1.

## 3. The matrix

- **Main** (assumptions hold): `H` ∈ {0, 2, 5, 10, 20 %} × `q` ∈ {15, 50, 85 %}
  × separation ∈ {weak, strong} × model ∈ {logistic, MLP}: 60 cells.
- **Broken assumptions**: `H` ∈ {5, 10 %}, `q` = 50 %, medium separation,
  mechanism ∈ {two-sided, feature-dependent} × both models: 8 cells.
- **10 repeats per cell**, each with its own population and seed (fixed and
  reproducible: seed = 1000 + 97 · cell index + repeat).

## 4. Measures (per cell and estimate)

Mean estimate, bias, MAE, RMSE (in percentage points of `H`), standard
deviation over repeats, the share of undefined and of capped estimates, the
share of runs with a memorisation warning, and running time.

## 5. Thresholds (assumptions hold)

| Criterion | Threshold |
|---|---|
| Zero truth (`H = 0`) | mean estimate ≤ 1 percentage point, and above 2 points in at most 10 % of repeats |
| Bias | at most ±2 percentage points or ±25 % of the true `H`, whichever is larger |
| MAE | at most 3 percentage points or 35 % of the true `H`, whichever is larger |
| Stability (`H` ≥ 5 %) | standard deviation over repeats at most half the true `H` |
| Undefined (medium and strong separation) | at most 20 % of repeats |

A cell passes for an estimate when every applicable threshold is met. Cells
with broken assumptions are reported, not judged; the report notes whether
the method warned.

## 6. What follows from the result

- **An estimate passes in nearly all main cells** (at least 90 %): JBG 1.2
  is accepted for that estimate; its observed error (MAE by target share and
  separation) becomes a documented uncertainty band shown with results. No
  further method work is needed for it.
- **Failures cluster** (for example rare target classes, weak separation, one
  model, or the in-sample estimates): those situations are documented and
  warned about, and targeted work from the plan (DN-03: out-of-fold `c`;
  DN-04/05: other estimators) is considered only for them.
- **Most cells fail**: the method needs the larger v2 work before its numbers
  are presented as estimates of a share.

## 7. Report

`results.csv` (one row per run and estimate), `summary.csv` (per cell and
estimate, with the verdict) and `thresholds.json`, plus a written summary
under `docs/dark_numbers/` with the conclusions.
