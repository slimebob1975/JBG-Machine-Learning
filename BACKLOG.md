# JBG Machine Learning - Active BACKLOG

This file lists open work only, with the rules for keeping it. Done work is
recorded in `CHANGELOG.md` (newest first). The BACKLOG as it stood at revision
300p, with every item and decision note since revision 188c, is kept unchanged
in `docs/backlog_archive_300p.md`. Each item says where it was asked or found.
A revision ticks the items it does (`[x]` with its revision number), and ticked
items leave this file at the next cleanup.

## Current priorities (decided 2026-11-18, reviewed 2026-11-23)

Stabilise before any new development: loose threads and bugs reported in use
first, everything else deferred. New development needs an explicit priority
decision.

### Now: stabilisation

- [ ] Bugs reported in use: added here as they are found.
- [x] 300v (asked 2026-11-24): default limits for c, 20 for the upper bound and
  10 for the warning level.
- [x] 300s (asked 2026-11-23): the Run tab showed nothing during the final
  training of the winning pipeline (the spot check's bar stayed full). It now
  has a bar of its own, moving with the time against the grid search's
  estimate.
- [x] 300s (asked 2026-11-23): a new dataset's name starts as the file's or
  table's name.
- [x] 300t (found 2026-11-24): two outdated or unclear passages in the
  user guides' Dark Numbers section.
- [x] 300u: the gate count. The Windows table (2026-11-24, 300t) and the
  container agree: 64 + 154 + 1186 = 1404 with `-Quick`, 1425 with the native
  group. The 1381 expected after 300p was a miscount (it was 1379).
- [x] 300u: the tested versions (agreed 2026-11-24): `constraints-tested.txt`
  and `docs/dependencies.md`. The requirements files stay unpinned.
- [x] 300w: the exact Python version, 3.13.7, in `docs/dependencies.md`.
- [x] 300s: Precision and Recall (micro, macro, weighted) failed on text
  classes with scikit-learn 1.9 (found 2026-11-23).
- [x] 300w: Average Precision scores probabilities and works with text
  classes. With two classes the positive class is the Dark Numbers target, or
  else the smallest class.
- [x] 300s: `.coverage` is no longer tracked, and `.gitignore` keeps it out.
- [x] 300x (decided 2026-11-24): the full rename to "JBG Machine Learning",
  in English in the masthead in both languages. The production repository is
  renamed by the user.
- [ ] The README still describes the Voilà GUI in most sections (found with
  300x). Rewrite it for the web GUI when Voilà's retirement is planned.
- [x] 300u: the gate's warnings and skips. The NumPy `RuntimeWarning` in the
  300k test came from a real fault: an infinite upper bound of c read 1, and
  the quality "reliable" (fixed). The skip is container-only: `dill` is
  installed on Windows, where the gate skips nothing.
- [ ] A pandas `FutureWarning` in `PredictionsHandler._update_dark_numbers`
  (found with 300y): joining an estimate's rows when some columns are empty or
  undefined. Harmless with pandas 2.3. Exclude the empty columns before joining.
- [ ] The interim configuration catalog (285d, design gap 10): project runs
  use the configuration repository since 288a, but the API still serves
  Voilà's saved configurations (`GET /api/configurations`,
  `JBGSavedConfigurations`), runs submitted by a Voilà configuration name and
  the SQL sign-in for a Voilà configuration. Nothing in the web GUI uses
  them. Remove them when Voilà is retired, which is not yet planned (kept,
  decided 2026-11-24). The open 285d item on marking unusable SQL
  configurations in that list goes with them.
- [ ] SQL acceptance (from 272 and 279ai): the container gate cannot test SQL.
  Agreed 2026-11-24: daily use of the web GUI on SQL projects covers most of
  `tests/SQL_REGRESSION_PROTOCOL_248.md` (written for Voilà). Rewrite it as a
  shorter checklist for the web GUI, and run it once when Voilà's retirement is
  planned.

### Pending decision

- [x] 300w (decided 2026-11-24): `D` is presented as an estimate, not a
  statistically proven share, on the Mörkertal view and in both guides.
- [ ] DN-06's decision on which estimators go on (300c, 300l). The user
  decides when.

### Deferred: future development (in rough order)

**Runs and results**

- [ ] Run history (Körhistorik, tab 8 of the design in
  `docs/gui/JBG_web_gui_design.md`). Kept (decided 2026-11-24) for what the
  Training and Results tabs do not have: rerun any run, compare two runs side
  by side, and the settings a run used against the current configuration.
- [ ] Pausing and resuming a feature investigation (299i; the engine keeps a
  snapshot), if Standard and Extended searches prove long.
- [ ] The group-disjoint holdout for more than two classes (noted with 298g):
  `JBGValidation148` refuses it ("Person-disjoint validation currently
  requires binary classification"). Grouped cross-validation has no such
  limit.
- [ ] The feature investigation for all classes at once (one against the rest
  for each class, shared folds, class-aware metrics and an aggregated
  ranking). Today more than two classes means the target class against the
  rest (299i).

**Configurations and datasets**

- [ ] If wanted: copy a configuration to another project (noted with 297d).
- [x] 300r (asked 2026-11-23): rename datasets and configurations.
- [ ] If wanted: switch a dataset to or from the prediction role (noted with
  298f; compatibility and column roles to settle).
- [ ] If wanted: in the roles form, choosing a second class or ID column
  could reset the former one in the browser (now refused on save, noted with
  298a).
- [ ] If wanted: durations between two date columns, choosing the date parts
  per column, and dates in other formats than ISO (noted with 298h).
- [ ] Rarely needed (agreed 2026-11-12): general ID handling in the engine's
  SQL path, so that uniqueidentifier and text IDs work as CSV IDs already do
  (row ordering, holdout split, writing predictions back, the key types of
  the result table). SQL ID columns are whole numbers only (298i).
- [ ] If wanted (from the Voilà P3 list): the row limit also as a percentage
  or a fraction. The web form takes a whole number, and empty reads all rows.

**Operation**

- [ ] Per-project retention (design decision 3): model files (288a), per-run
  result folders (295a) and the CSV file versions from corrections (299b) are
  kept until deleted (299e, 299f).
- [x] 300w (decided 2026-11-24): keeping SQL sign-ins across server restarts
  is not needed. The browser keeps the credentials, so signing in again is one
  click.
- [ ] The language choice stored per user on the server (design decision 6).
  Today it is a browser cookie (`jbg_lang`).
- [ ] A live pipeline picture (listed 2026-11-18, to be described when it
  comes up; the configuration's pipeline picture is 298e).

**Dark Numbers** (the plan `docs/dark_numbers/JBG_Dark_Number_Analysis_2_0_Implementeringsplan.md`, the contract `DN-01_method_contract.md`)

- [ ] A production-like synthetic dataset for the validation study, generated
  from aggregated profiles (2026-11-19). The generator and summary received
  then stay outside the repository.
- [ ] Sampling sliders (asked 2026-11-16, specified 2026-11-24), one in the
  Oversampling and one in the Undersampling section, for the ordinary pipeline
  and the correction test. The slider sets the target class's share after
  sampling. It starts at the class's current share (minority or majority) and
  moves only towards 50 %: oversampling from below, undersampling from above,
  never past 50 % or back past the current share. With more than two classes
  the sliders are tied to the smallest or the largest class. One value applies
  to every chosen sampler that can use it. A sampler that cannot uses its
  default, and the user is told. The undersampling presets (R20, R10, R05,
  R02) are removed.
- [ ] DN-05: mixture-proportion estimation (PU-SCAR, calibrated
  probabilities), tested with the study before any engine work (300c).
- [x] 300y (specified 2026-11-24): logistic regression in place of the
  pipeline's algorithm (only the algorithm is replaced) for the whole Dark
  Numbers computation when `c` is above the upper bound or cannot be estimated.
  On by default, with a checkbox in the Mörkertal section, always reported.
  Not wanted (2026-11-24): `c` for each pipeline in the model comparison. The
  test-data performance is enough for choosing a pipeline.
- [ ] If wanted: the memorisation rule as settings. It is still fixed in
  `JBGDarkNumbers.py` (fit 0.95 and a gap of 5 percentage points, 0.99 without
  an unseen accuracy).
- [ ] An adaptive flip fraction, adjusted to the class size, settable in the
  Dark Numbers section (asked 2026-11-18; a fixed 0.2 by default today).
- [ ] Dark Numbers per subgroup of a categorical column, chosen in the Dark
  Numbers section (asked 2026-11-18). First version: one estimation for the
  whole population, divided among the categories in proportion to each
  category's alpha-weighted false positives, with a minimum category size,
  shown per category and in the growth view. Then several levels, each first
  level group with its own complete estimation. The full description is in
  the archive.
- [ ] For v2: `c` on the cross-trained model's own test part within its
  all-data estimate.
- [ ] DN-04: mislabelling and sensitivity analysis.
- [ ] DN-07, what remains: choosing the method in the interface. The settings
  and the results are in place (298c to 300n).
- [ ] DN-08: a controlled production pilot, after the method has settled.

**Modelling and performance** (ideas from the Voilà era that still apply to
the engine, not scheduled)

- [ ] Search budget and cost: measure fit counts, time and memory, and
  improve the time estimates for Quick, Standard, Extended and Custom (178).
- [ ] Feature-search parallelism: compare requested and actual workers,
  process counts and time for the same budget (279n).
- [ ] Investigation row limits: reproduce the 200-row class-support failure,
  and compare bounded selection with stratified sampling (279n).
- [ ] Resource handling: costly Nystroem and MLP combinations, threads against
  processes, before changing concurrency defaults.
- [ ] Optional fold checkpoints for expensive feature-search candidates.
- [ ] A composite model-selection objective that aggregates ranks per metric
  (MCC, balanced accuracy, ROC-AUC), beside single-metric selection.
- [ ] High-dimensional feature search: subset-size coverage and nested
  cross-validation.
- [ ] New estimator families as opt-in candidates: XGBoost first, then
  fastai, and native CatBoost in the ordinary search only with pipeline-local
  encoders.

**Platform**

- [ ] A replaceable DataLayer contract for SQL, CSV and future sources
  (capabilities, dataset identity and revisions, reading, results, corrections,
  authorization).
- [ ] Package structure: move the flat `src/` layout into subpackages by
  responsibility, and split modules with mixed responsibilities, `JBGMeta.py`
  first, behind stable import facades.
- [ ] htmx and Fluent web components (design decision 2), pinned with
  integrity hashes, with the first view that needs client-side behaviour. The
  interface uses plain JavaScript (294a) and charts drawn on the server
  (299k) so far.
- [ ] `fastapi_offline` and the offline Swagger setup (282b) are temporary and
  may be replaced. The interface itself makes no requests outside the server
  since 300j.
- [ ] Microsoft Entra ID when the Azure deployment begins, with server-side
  authorization, project isolation, credential handling, sessions, retention
  and audit designed before any multi-user rollout. Keep the simple access
  model (design decision 5): SQL rights come from each user's own login, and
  JBG only keeps principals' projects and runs apart. Validate deployment,
  secrets and storage against the actual hosting.

## Standing rules

- Every revision has a CHANGELOG entry (newest first), an update here, a row
  in the design log (`docs/gui/JBG_web_gui_design.md`), tests in
  `tests/test_revision_<rev>_*.py` (the gate takes revision 280 and up), the
  user guides (`docs/user_guide.sv.md`, `docs/user_guide.en.md`, one section
  per tab) kept in step, and a short "how to try it".
- The full gate (`scripts/run_backend_refactor_tests.ps1`) for engine, worker,
  storage or configuration changes, and at least every fifth revision. `-Quick`
  for interface and documentation changes.
- Privacy: no production catalog, schema or table names, personal data or
  production profiles in the repository, and no runtime logs, datasets, SQL
  text or credentials. Run `scripts/check_documentation_privacy.py` (with the
  local private blocklist) before each commit.
- Swedish texts (`sv.po`, the Swedish user guide) use a comma or a dash
  instead of a semicolon (299m). The one exception is the list of alphas in
  the Dark Numbers calculation table (299f2), where the comma is the decimal
  sign. "Fold" is "del" and "delar", "out-of-fold" is "osedd del" (300i).
- Engine changes must not break the Voilà interface until it is retired. New
  Config fields go in `Config.LATER_KEYS`, server-owned fields in
  `SERVER_OWNED`.
- The regression suite is a safety net: add tests that protect new changes or
  reproduce real failures.

## Closed in the 300q cleanup

The items below were open in the 300p BACKLOG (see the archive) and are
closed here.

- Done, though still unticked:
  - why a run failed, on the Training and Prediction tabs (297e);
  - the result views: model comparison (295a), predictions (296b), paged
    mispredictions with `mispredicted_count` labelled as all labelled rows;
  - the application layer, the FastAPI server and the web interface in its
    phases (284a to 300p), including Voilà retirement items 1 to 4
    (299a to 299j);
  - SQL and CSV as peer data sources (257 to 279n, and in the web interface
    since 288a);
  - the commit and tag of release 0.19.1 (recorded in the archive);
  - DN-01 to DN-03 and the DN-06 validation study (299n to 300c).
- Superseded by the web interface:
  - the CSV enabling and gating steps of revisions 184 to 259;
  - Voilà parity (273a, 273b) and its end-to-end checks in Voilà;
  - Voilà controls: the Model selection label, the integer class-column
    filter, the reclassification widget density, auto-scrolling of
    multi-selects, automatic project names, the CSV "Erase model" button, the
    Regr. test and Regr. suite buttons;
  - Voilà runtime containment, Voilà pause and resume with two workers, the
    revision-176 smoke tests in Voilà, the saved-CSV "Artifact not found" in
    Voilà (279n), Voilà's combined CSV limit and its SQL "Erase models"
    (models are deleted in the web interface since 299e).
- Superseded by later decisions:
  - "Dark Number methodology parked" (reopened 2026-11-16 as JBG Dark Number
    Analysis 2.0);
  - the binding phase order after revision 272 (completed);
  - the old definition of done (now the standing rules above);
  - the link to `docs/backlog_archive_pre_152.md`, which is no longer in the
    repository.
- Not planned (decided 2026-11-09): importing models trained in Voilà into
  the model catalog.
