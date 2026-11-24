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
- **F5. With more than two classes, flipped rows go to one class:** *(settled in v1.1, section 9)* the first
  other class in sorted order, not "the rest" or a random other class, though
  the log says "flipped to non-target labels".
- **F6. `c` depends on the computer.** *(Settled in v1.1, section 9.)* `n_splits × n_repeats` is chosen from
  the CPU count (`_auto_n_splits_and_repeats`, at least 4 × 2), so the same
  data can give different `c` on different machines. Within one repeat, all
  folds use the same random seed for drawing flips.
- **F7. Alpha is the certainty of the predicted label** *(settled in v1.1, section 9)*, not the probability
  of `T`: for an FP row the probability of `T`, for an FN row the probability
  of the (wrongly) predicted other class.
- **F8. `D` is not a proportion.** *(Settled in v1.2, section 9.)* Its range is `[0, 2c]` (`base`) and larger
  with F1. The plan therefore reports `D_JBG` separately from `H`/`U` until a
  translation is validated.
- **F9. Two of four estimates are in-sample** *(settled, section 9)* (`D_cv_full` partly,
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
  (300v: the default upper bound is 20, see "Settings and the overtraining
  warning" below.)
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
be too high. 299q2 (settled 2026-11-16) sharpens the rule: the fit is
compared with the accuracy on unseen rows (the cross-trained model's test
part), and the warning is given when the fit is at least 0.95 and at least 5
percentage points above it (`MEMORISATION_FIT`, `MEMORISATION_GAP`); an easy
problem gives high values for both and is not flagged. Without an unseen
accuracy, the fit-only rule (0.99) applies. The fit is reported beside `c` (`corr_train_fit`). No number
changes. For example, a decision tree fits 100 % of its training rows and
recovers 0 % of the flipped rows (`c` infinite, undefined by v1.1).

**The v2 definition (for DN-03).** Recovery is measured out-of-fold: a
fraction of the target rows is relabelled once over the whole dataset; each
relabelled row is predicted by a model trained on the other folds; `r` is the
share of relabelled rows predicted as the target, and `c = 1/r̄` within
v1.1's bounds. This is the label frequency of positive-unlabelled learning
(Elkan and Noto, 2008), which DN-05 also builds on.

### F5 (299r, settled 2026-11-16, option A): multiclass flips

With more than two classes, each flipped row gets a random other class, drawn
in proportion to the other classes' sizes in the training part, as
mislabelling into "the rest" would look (reproducible with the seed). It
always got the first other class in sorted order, so `c` depended on the
class names. Two-class results are unchanged.

### F6 (299s, settled 2026-11-16, option A1): fixed folds and repeats

The flip test uses 4 folds × 2 repeats on every computer
(`FLIP_TEST_FOLDS`, `FLIP_TEST_REPEATS`); the CPU count only sets how many
folds run at the same time. It was chosen from the CPU count, so `c` differed
between machines (synthetic data, logistic regression: 2.71 to 3.15).
2-, 4- and 8-core machines already used 4 × 2 and are unchanged. The repeats
still reuse the same folds (only the flip draw changes); fresh folds per
repeat and more repeats for a steadier `c` belong to v2 (DN-03), and folds and
repeats may become settings in "Mörkertal: avancerat".

### F7 (299t, settled 2026-11-16, reading 1): alpha target against the rest

Alpha weighs each error by the model's certainty in its verdict, target
against the rest, like the rest of the formula: `α_FP = mean P(T)` over false
positives (as before) and `α_FN = mean (1 − P(T))` over false negatives (it
was the probability of the predicted class, which with more than two classes
is less than the certainty that the row is not `T`). Single alpha mixes the
two the same way. The combined estimate takes each row's probabilities from
the model it takes the row from. Two-class results are unchanged. The
probabilities are model scores, not calibrated probabilities; calibration
belongs to v2 (DN-05).

### JBG v1.2 (299u, settled 2026-11-16): F8 and the reading of the equation

Agreed in discussion (results change in normal cases, hence a new version,
`METHOD_VERSION = "1.2"`):

- **What `D` estimates.** The hidden share `H = P(Y=T | S≠T)`: of the rows
  registered as another class, the share that really are `T`. Without
  weights and correction, `D₀ = min((1 − TN_r)(2 − TP_r), 1)`.
- **The first factor** `1 − TN_r = FP/(FP+TN)`: the candidates for hidden
  cases among the rows registered as not `T`.
- **The second factor** `2 − TP_r = 1 + FN/(TP+FN)`: a model that misses known
  `T` cases also misses hidden ones, so the candidates are scaled up. It is
  the linear approximation of `1/TP_r` near `TP_r = 1`, more restrained for
  weak models. Not divided by two: with perfect detection `D₀ = FPR`.
- **Capped at 1** with a flag (`capped`): above 1 the estimate has broken
  down for that target.
- **The alphas are soft counting.** `α_FP · FP` is the expected number of
  real `T` cases among the false positives. `α_FN` weighs the misses only:
  `1 + α_FN (1 − TP_r)`; it multiplied the whole factor, so with no misses a
  low `α_FN` still pulled `D` down.
- **`c` corrects in-sample estimates for memorisation.** A model trained on
  rows reproduces their registered (wrong) labels, which suppresses exactly
  the false positives `D` counts; `c = 1/r` from the flip test measures that
  suppression. It is used for the estimates on all data and not for the
  unseen test part (source "not applied (test part)"). This matches the
  practical experience that `c` is large for models prone to overtraining.

The standard equation (linear, separated alpha):

`D = min(c_scope · α_FP · (1 − TN_r) · (1 + α_FN · (1 − TP_r)), 1)`, with
`c_scope = c` in-sample and `1` on the test part.

The single-alpha and non-linear forms keep their shape (not reviewed), with
the same cap and the same use of `c`. The Results tab shows the equation the
run used with each part explained, and the user guide (About tab) explains
the method in detail.

### F9 (299w, settled 2026-11-16): four model variants, sorted

The four estimates are model variants that together form an interval with
subintervals. They are kept and shown sorted from the lowest to the highest
(undefined last), each labelled with its model variant, with the subintervals
listed. There is no order check: after 299u, `c` corrects the in-sample
variants, so no order follows from the method. Noted for v2: the
cross-trained model's estimate on all data is multiplied by `c` also on its
own unseen test part (about a fifth of its rows), a modest over-correction.

### The result format (299x, settled 2026-11-16)

Every Dark Numbers computation writes a JSON record next to the CSV files,
which stay unchanged (`dark_numbers_<…>.json`, `JBGDarkNumberRecord`):
`schema_version` (1), the method and its version (JBG 1.2), the parameters
used (calculation type, method, alpha, target class, flip fraction, folds and
repeats, the bounds on `c`, the cap, the memorisation rule, the root `k`, the
random seed), and one entry per estimate: method, scope (model variant),
model, target, estimand (`D_JBG`; v2 adds `H`, `U`, `N_hidden`), value,
interval (none in v1.2), status (ok, capped, undefined) and reason. Runs
without a record were computed with an earlier version; the Results tab shows
their values as saved, with a note instead of the equation.

### DN-02 (299y, settled 2026-11-16): sampling in the flip test

The flip test has its own sampling policy (`mode.dark_number_sampling_policy`,
`JBGDarkNumberSampling`): PIPELINE (default, the winning pipeline's own
sampling, as before), NONE, SMOTE, CLEAN_SMOTE (synthetic rows only from
unflipped rows, parents and neighbours; with fewer than k + 1 = 6 clean rows
in a class to oversample, that fold uses NONE and is flagged) and UNDER (1 : 1
to the smallest class). The other policies switch the pipeline's sampler
steps off in the copy and resample the flipped training part only. With
PIPELINE, an oversampling pipeline and a majority target, the log and the
Results view warn of contamination. The policy, synthetic rows, fallback
folds and the risk are stored in the result record. Ordinary training is not
affected. On synthetic data with an 86 % majority target and SMOTE in the
pipeline (logistic regression), `c` was 1.67 as the pipeline, 1.06 with
NONE, 1.52 with CLEAN_SMOTE. Which policy should be the recommendation is
DN-06's benchmark; ratio controls are in the backlog.

### DN-03 (300e, settled 2026-11-18): the out-of-fold correction factor

`c` is also measured out-of-fold (`JBGDarkNumberOutOfFold`): the configured
flip fraction of the target rows is relabelled once (to other classes by
size), five stratified folds, each relabelled row predicted by a model trained
on the other folds; `r` the share recovered, `c = 1/r`. At least 3 and at most
10 repeats, stopping when the 90 % interval of `c` (a t-interval on the
recoveries) is within ±10 % of `c`. Quality: reliable (1 ≤ c ≤ 10, interval
within ±25 %), uncertain (wider: used, flagged), not estimable (outside 1–10
or not computable: undefined). The sampling policy of DN-02 applies here too.

During the transition (agreed 2026-11-18) the Dark Number keeps the in-sample
`c`. The out-of-fold `c`, its interval and quality, and the Dark Number it
would give (`dark_number_oof`) are shown beside it, stored in the record, and
measured by the validation study (`D_oof`, same thresholds). The switch is
decided from experience and the study. A first look: for logistic regression
the two `c` are close (about 1.6), so `c` alone does not explain the study's
in-sample overestimates.

### DN-03 revised (300g, 2026-11-19): measured inside the flip test

300e's separate computation (5 folds, 3–10 repeats, one fit after another)
took many hours on large data. The out-of-fold `c` is now measured inside the
existing flip test at no extra fit: each of its 4 × 2 folds trains a copy on
75 % of the rows with some target rows relabelled, and that copy also predicts
the fold's unseen target rows. A model cannot see the label of a row it was
not trained on, so the share it still predicts as the target is the recovery a
relabelled row would have had. `c = 1/r` over the 8 fold values, with a 90 %
t-interval and the same quality states. The in-sample `c`, and so the v1.2
Dark Number, are unchanged. The flip test shows its progress fold by fold.

### JBG 1.3 (300l, settled 2026-11-19): c is the overtraining factor

`c` mixed the model's ordinary misses (already counted by
`1 + α_FN (1 − TP_r)`, so counted twice) with overtraining, what `c` was
introduced for. Since 1.3:

`D = min(c · α_FP · (1 − TN_r) · (1 + α_FN · (1 − TP_r)), 1)`, with
`c = max(1, mean(r_unseen) / mean(r_in))` over the flip test's 8 parts (300m:
the ratio of the means, so one part with `r_in = 0` does not make `c` infinite)

on the estimates on all data (the test part uses no `c`). Both recoveries come
from the same models trained with the same relabelled rows, so the ordinary
misses and the effect of the relabelled labels cancel in the ratio; what is
left is memorisation. `c` keeps the bounds 1–10, gets a 90 % interval and a
quality state, and the calculation table shows its two parts (`1 / r_in`, the
former `c`, and `1 / r_unseen`). A fallback estimate (regression or
perturbation) has no parts, so `c` is then not estimable. In the validation
study the three estimates on all data passed in 7–8 of 52 cells instead of
1–2, with the same error as the test-part estimate (report, second run).

### Settings and the overtraining warning (300n, 2026-11-20)

The flip test's repeats (default 2, 1–10), the upper bound for `c` (default
10) and the warning level for overtraining (default 2) are configuration
settings, stored with each result.

Changed 2026-11-24 (300v, the user's decision): the defaults are 20 for the
upper bound and 10 for the warning level. 10 and 2 proved too limiting in
daily use. Under JBG 1.3 (`c = mean(r_unseen) / mean(r_in)`) an upper bound
of 20 means the model must recognise at least one twentieth as large a share
of its relabelled training rows as of the target rows it has not seen.
Configurations keep the values they were saved with. The warning is given when `c` is above the
level: the model learns some of the deliberately wrong labels by heart for
the target class. It replaces the overall-fit rule as the main signal (that
rule stays as a second trigger), since overall accuracy is dominated by the
majority class: a real run with 1:100 classes and `c` ≈ 2–2.8 showed a fit of
100 % against 99.5 % and no warning.
