# Validation of JBG 1.2 against a known truth – report

Study run 2026-11-18 by the protocol in `DN-06_v12_validation_protocol.md`
(thresholds approved 2026-11-16, unchanged; 52 feasible main cells and 8 with
broken assumptions, 10 repeats each, 600 populations, no failed runs).

## 1. Verdict

JBG 1.2 does **not** estimate the hidden share. Of the 52 main cells, where
the method's own assumption holds (cases hidden one way only), the estimates
pass the thresholds in:

| Estimate | Cells passed (of 52) |
|---|---|
| Cross-trained model, test data | 8 |
| Cross-trained model, all data | 2 |
| Final model, all data | 1 |
| Combined | 1 |

By the protocol's rule ("most cells fail"), the method needs the larger work
before its numbers are presented as estimates of a share.

## 2. What the numbers show

**The Dark Number is mostly the model's own error level, not the hidden
share.** With nothing hidden (true share 0), the test-part estimate was:

| Target share | Strong separation | Weak separation |
|---|---|---|
| 15 % | 2 % | 0–0.4 % |
| 50 % | 8–9 % | 29–31 % |
| 85 % | 24–26 % | 80–81 % |

The same pattern holds at every true share: the estimate is set by the target
share and how well the classes separate, and moves only a little with the
truth. With 50 % target share and strong separation, the test-part estimate
went from 8.8 % to 15.6 % as the truth went from 0 % to 20 %, about a third of
the change. With weak separation it even fell (from 30 % to 10.5 %) as the
truth rose: more hidden cases make the model predict the target less often.

**Why.** The first factor, `FP / (FP + TN)`, counts every row registered as
"rest" that the model calls the target, whether a hidden case or an ordinary
model error. When the classes overlap, or when the target is the majority (the
model then calls many rows the target), the model's own errors dominate and
the hidden cases are a small part of what is counted. Nothing in the formula
separates the two.

**The correction factor makes the in-sample estimates worse.** `c` was 1.25
in the median, 1.76 on average and up to 9.2. It multiplies estimates that
are already too high, so the three in-sample estimates passed in only 1–2
cells. With weak separation and a 50 % target share they reached 96–100 %.

**Where it passed.** Rare target classes (15 %) with small true shares, and a
few cells with 50 % target share and strong separation: situations where the
model makes few false positives of its own.

**Broken assumptions** (reported only): with two-sided mislabelling the
test-part estimate overstated by 13–19 percentage points, with
feature-dependent hiding by 6–16.

## 3. A standard alternative, tried outside the engine

As a check of what a method with a defined target can do on the same data,
the positive-unlabelled estimator of Elkan and Noto (2008) was tried on a
subset (logistic regression, out-of-fold probabilities, 5 repeats). It rests
on the same one-sided assumption. Results:

- **Strong separation:** it follows the truth much better (with 50 % target
  share: 8.8, 12.8, 17.1 and 25.2 % for true shares 0, 5, 10 and 20 %, a slope
  of about 0.8 against JBG's 0.35), but with an offset of 5–13 points from
  the overlap between the classes.
- **Weak separation:** it fails just as JBG does (64–79 % throughout).

This points to a limit no formula escapes: **when the classes overlap
strongly, a hidden case cannot be told from a look-alike of the other class.**
Any method needs good separation, and a way to fix the zero level, to
estimate the hidden share. Methods built for this (mixture-proportion
estimation, for example TIcE or KM2, which assume part of the "rest" is
certainly not the target) are the next candidates.

## 4. Consequences

1. **For users now:** the Dark Number should not be read as the share of
   hidden cases, and the growth view ("Tillväxt för målklassen") turns it
   into a count it cannot support. It is at best an index of how much the
   model disagrees with the register, comparable only between runs on the
   same data with the same settings.
2. **For the method:** improving `c` (DN-03) does not fix this, since the main
   error is in the first factor. The work that matters is an estimator with a
   defined target and a fixed zero level (DN-05, mixture-proportion
   estimation), tested with this same study before it is put in the engine.
3. **The study code** (`JBGDarkNumberStudy`) is the ready test bench for any
   candidate: the same populations, seeds and thresholds.

## 5. Second run (2026-11-19): c on the unseen part and the overtraining factor

The same 600 populations (300k), judged by the same thresholds, with two more
variants of `D` for the estimates on all data: with `c` measured on the unseen
part (DN-03), and with the overtraining factor `c_over = c / c_unseen`.

| Estimate | D (1.2) | D with c on the unseen part | D with c_over |
|---|---|---|---|
| Cross-trained model, test data | 8 | 8 | 8 |
| Cross-trained model, all data | 2 | 2 | 8 |
| Final model, all data | 1 | 1 | 7 |
| Combined | 1 | 1 | 8 |

- `c_over` was about 1 for both models (median 1.00 for logistic regression,
  1.02 for the MLP; the former `c` had medians 1.25–1.4 and reached 9). The
  error of the estimates on all data fell from 38 to 24 percentage points on
  average, the level of the test-part estimate; with 50 % target share and
  weak separation the final model's estimate went from 98.5 % to 24.2 %.
- `c` on the unseen part alone did not help: it was nearly as large as the
  former `c`, since what inflated it here was the ordinary misses, not
  memorisation. The ratio is what matters.
- What remains is common to all four estimates: the model's own false
  positives in the first factor, large with a majority target class or weak
  separation.
- The hit rate held: the flagged rows held on average about 4.5 times more
  true hidden cases than random selection.

Decision 2026-11-19: `c_over` replaces `c` as JBG 1.3 (300l).
