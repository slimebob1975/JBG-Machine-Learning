# DN-01 – Method contract and baseline for JBG Dark Numbers (v1)

Status: **for review** (2026-11-16). Part of the plan in
`JBG_Dark_Number_Analysis_2_0_Implementeringsplan.md` (DN-01). By the plan's
own gate, no engine code changes until this contract has been reviewed. This
revision changes no engine code: it describes the method as implemented and
freezes it with characterisation tests
(`tests/test_revision_299n_dn01_baseline.py`), so later revisions can prove
that the original method (JBG v1) is unchanged.

Baseline revision: 299m (the code as of this contract). Only synthetic data
is used; no production data or names.

## 1. Where the method lives

| Part | Code |
|---|---|
| Formulas, rates, alpha weights | `src/JBGDarkNumbers.py` – `DarkNumberCalculator` |
| Correction factor `c` (flip test) | `src/JBGDarkNumberCorrectionFactor.py` – `evaluate_split`, `DarkNumberCorrectionFactorEstimator` |
| Orchestration: estimates, `c` per target, fallbacks | `src/JBGHandler.py` – `get_dark_numbers`, `_calculate_dark_number_corrections`, `_auto_n_splits_and_repeats` |
| Experimental fallback (opt-in) | `estimate_perturbed_same_model_correction` (`JBGDarkNumberCorrectionFactor.py`), `JBGDarkNumberExecution.py` |
| Regression fallback | `src/JBGDarkNumberCorrectionRegressor.py` (to be described at review) |
| Display, formula text | `get_formula_spec`, `JBGWebUIDarkNumbers.py`, Results → Dark Numbers |

## 2. Notation (as implemented)

For one target class `T`, every class other than `T` counts as negative
(one-vs-rest on the true and predicted labels).

| Symbol | Code | Meaning |
|---|---|---|
| `TP, FP, FN, TN` | `confusion_matrix(real, predicted).ravel()` | Counts for target vs rest |
| `TP_r` | `TPr = TP/(TP+FN)`, else **−1** | True positive rate (recall of `T`) |
| `TN_r` | `TNr = TN/(TN+FP)`, else **−1** | True negative rate; `FPR = 1 − TN_r` |
| `p_i` | `max(predict_proba(x_i))` | Certainty of the predicted label of row `i` |
| `α` | mean `p_i` over rows with `real ≠ predicted` (else 1) | Single alpha |
| `α_FP`, `α_FN` | mean `p_i` over FP rows, over FN rows (else 1) | Separated alpha |
| `k` | `root_degree` (default 3) | Root of the non-linear form |
| `c` | `1 / mean(r)` | Correction factor (`c_JBG`) |
| `r` | share of flipped rows predicted back as `T` | Recovery in the flip test |
| `D` | `dark_number` | The reported JBG quantity (`D_JBG`) |

## 3. Formulas (exact branches)

| Method / alpha | Branch | `D` |
|---|---|---|
| LINEAR / NONE | `base` | `c · (1 − TN_r) · (2 − TP_r)` |
| LINEAR / SINGLE | `single_alpha` | `c · α · (1 − TN_r) · (2 − TP_r)` |
| LINEAR / SEPARATED | `separated_alpha` | `c · α_FP · (1 − TN_r) · α_FN · (2 − TP_r)` |
| NON_LINEAR / NONE | `non_linear` | `c · (1 − TN_r^{1/k}) · (2 − TP_r^{1/k})` |
| NON_LINEAR / SINGLE | `non_linear_alpha` | `c · α · (1 − TN_r^{1/k}) · (2 − TP_r^{1/k})` |

NON_LINEAR / SEPARATED is not implemented (raises). A target with no false
positives (`FP = 0`) on a scope with both target and rest rows gives `D = 0`
whatever `c` is; the correction is then skipped ("not_needed_zero_fp").

## 4. The correction factor `c` (flip test, `predict` mode)

For each target `T`, with the model's estimator cloned:

1. `n_splits × n_repeats` stratified folds over all rows (`sample_size = 1.0`).
   **The test part of each fold is not used**; a fold only selects the rows
   the test runs on.
2. In the training part, `n_flip = ⌊f · #(rows of T)⌋` rows of `T`
   (`f = flip_fraction`) are drawn without replacement and relabelled.
3. The clone is fitted on the relabelled training part and predicts **the
   same flipped rows it was fitted on**. `r` = share predicted as `T`.
4. `c = 1 / mean(r)` over all folds and repeats. Status "estimated" when
   finite and positive, otherwise "zero_recovery"/"nonfinite"/"nan_recovery";
   too few rows of `T` gives "insufficient_sample" and `c = 1` (not used).

## 5. The four estimates

| Estimate | Model | Rows |
|---|---|---|
| `D_cv_test` | cross-trained model | test part only |
| `D_cv_full` | cross-trained model | all rows (**includes its training rows**) |
| `D_retrained_full` | final model, retrained on all data | all rows (**in-sample**) |
| Combined (legacy full-data) | per row, the error with the highest certainty across the models (correct everywhere: true label, `p = 0`) | all rows |

## 6. Findings: code vs. method description

Numbered for review. Each is frozen as current behaviour by the tests and is
**not** fixed here.

- **F1. Undefined rates enter the formula.** *(Settled in v1.1, section 9.)* With no negatives (no positives)
  `TN_r` (`TP_r`) is −1, so `1 − TN_r = 2` (`2 − TP_r = 3`) instead of an
  undefined result; in the non-linear form the root of −1 gives a complex
  number, which is reported as it is.
- **F2. A scope with one label only** *(settled in v1.1, section 9)* makes `confusion_matrix(...).ravel()`
  return one value, and the four-way unpacking raises.
- **F3. A fold with no flips counts as recovery 0.** *(Settled in v1.1, section 9.)* `evaluate_split` returns
  0.0 when `n_flip = 0` instead of leaving the fold out. With few target rows
  this pulls `mean(r)` down and `c` up, a candidate cause of extreme factors
  such as the `c ≈ 8237` in the plan's background case.
- **F4. Recovery is in-sample.** *(Settled in v1.1 as a warning, section 9.)* The flipped rows are part of the training
  data the clone is fitted on, so `r` measures how strongly the model resists
  memorising wrong labels, not how well it finds hidden cases in new data.
  The estimand of `c` follows from this (plan step 5).
- **F5. With more than two classes, flipped rows go to one class:** the first
  other class in sorted order, not "the rest" or a random other class, though
  the log says "flipped to non-target labels".
- **F6. `c` depends on the computer.** `n_splits × n_repeats` is chosen from
  the CPU count (`_auto_n_splits_and_repeats`, at least 4 × 2), so the same
  data can give different `c` on different machines. Within one repeat, all
  folds use the same random seed for drawing flips.
- **F7. Alpha is the certainty of the predicted label**, not the probability
  of `T`: for an FP row the probability of `T`, for an FN row the probability
  of the (wrongly) predicted other class.
- **F8. `D` is not a proportion.** Its range is `[0, 2c]` (`base`) and larger
  with F1. The plan therefore reports `D_JBG` separately from `H`/`U` until a
  translation is validated.
- **F9. Two of four estimates are in-sample** (`D_cv_full` partly,
  `D_retrained_full` and Combined fully), which matters when they are read as
  a range together with `D_cv_test`.

## 7. Frozen baseline (characterisation tests)

`tests/test_revision_299n_dn01_baseline.py` pins, on synthetic data:

- all five formula branches for three targets (exact values);
- F1, F2 (undefined rates; one-label scope), F3 (zero flips → 0.0), F5 (the
  first other class receives the flips), F6 (folds and repeats for 4, 8, 12
  cores), F7 (alpha from the predicted label's certainty);
- the flip test end to end with a rule-based stand-in model (exact recovery
  per fold and `c`, independent of library versions), and with logistic
  regression within a range.

A later revision that changes any of these numbers must say so and update
this contract.

## 8. To decide at review (before DN-02)

1. Which findings (F1–F9) are defects of v1 to keep as they are (v1 frozen)
   and which are design inputs for JBG v2 (DN-03).
2. The estimand of `c` (F4): keep in-sample recovery for v1 and define an
   out-of-sample variant for v2, as the plan's two recovery measures suggest.
3. Reproducibility (F6): fixed folds and repeats for v2, independent of the
   CPU count.
4. Result format and schema version for v2 results (plan step 4).
5. The exact specification of CLEAN_SMOTE and undersampling (plan step 6), to
   be written with DN-02.
6. Benchmark measures and decision rules (plan step 7), fixed before DN-06.

## 9. Settled at review

### JBG v1.1 (299o, settled 2026-11-16): F1, F2 and the bounds on `c`

A correction of the standard method that leaves `D` unchanged in every normal
case (`DarkNumberCalculator.METHOD_VERSION = "1.1"`):

- `FP = 0` gives `TN_r = 1` and `D = 0`; `FN = 0` gives `TP_r = 1`. As before.
- If `TN + FP = 0` or `TP + FN = 0`, a rate is undefined and `D = −1`
  ("undefined"), in every branch. This also covers a scope with one label
  (F2), which raised before. The pipeline and/or the dataset are ill chosen
  for that target.
- `c` must satisfy `1 ≤ c ≤ c_max` with `c_max = 10`, that is the model must
  recover at least 10 % of the flipped rows (a recovery below that cannot be
  told from chance in an unstable setting). Otherwise `c = −1` and `D = −1`.
- If `c` cannot be estimated (it was silently 1.0, "fallback/unestimable"),
  `c = −1` and `D = −1`: the pipeline is ill-suited to the problem.
- With `FP = 0` and rows outside the target, `D = 0` whatever `c` is.

Since a valid `D` is never negative, −1 cannot be mistaken for a value. The
Results tab shows "Odefinierad" with the cause. Later (backlog): an opt-in
standard estimator for `c` (for example logistic regression with standard
scaling), chosen in the GUI, when the pipeline's own `c` is unusable.

### F3 (299p, settled 2026-11-16): folds without flips

A fold with no flipped rows measures nothing and is left out of the mean
(it counted as recovery 0). At least half of all folds must have flipped
rows; otherwise `c` cannot be estimated, so `c = −1` and `D = −1`.

Found while patching: in the main path F3 does not occur. The minimum number
of target rows checked before the flip test, `max(⌈3/f⌉, 2 · folds)`,
leaves at least two flips in every fold's training part. F3 therefore does
not explain extreme factors such as `c ≈ 8237`; the likelier cause is F4: a
flexible model fitted on the flipped rows reproduces their wrong labels on
those same rows, so recovery is near zero and `c = 1/r` explodes. The fix
stays as a guard for direct use of the flip test.

### F4 (299q, settled 2026-11-16, option C): in-sample recovery

v1.1 keeps in-sample recovery (the v1 reference is unchanged), and warns when
it is likely misleading. The flip test also measures the fitted copy's fit to
its own unflipped training rows (one extra prediction, no extra fitting). At
0.99 or more (`MEMORISATION_THRESHOLD`) the model is taken to memorise its
training rows; the log and the Mörkertal view then say that `c` and `D` may
be too high. The fit is reported beside `c` (`corr_train_fit`). No number
changes. For example, a decision tree fits 100 % of its training rows and
recovers 0 % of the flipped rows (`c` infinite, undefined by v1.1).

**The v2 definition (for DN-03).** Recovery is measured out-of-fold: a
fraction of the target rows is relabelled once over the whole dataset; each
relabelled row is predicted by a model trained on the other folds; `r` is the
share of relabelled rows predicted as the target, and `c = 1/r̄` within
v1.1's bounds. This is the label frequency of positive-unlabelled learning
(Elkan and Noto, 2008), which DN-05 also builds on.
