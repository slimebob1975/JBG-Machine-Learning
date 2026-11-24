# JBG Automatic Classification

The program trains machine learning models that sort the rows of a table
into classes. It learns from rows that already have a class and can then
suggest a class for rows that lack one. Data come either from a table in SQL
Server or from a CSV file.

When training, the program compares several algorithms and combinations of
preprocessing, evaluates them on data kept out of the training and saves the
best model. The model can then be used for prediction, that is, to classify
new rows.

## The work order

The tabs follow the work order from left to right:

1. **Projects**: create or open a project.
2. **Dataset**: add data, set the column roles and validate.
3. **Configuration**: choose the machine learning settings.
4. **Training**: start a training run and follow it.
5. **Results**: review how good the model turned out.
6. **Models**: choose the model to use.
7. **Prediction**: classify rows without a class.

The line below the title shows the current work: the open project, the
active training dataset, the configuration chosen for runs and the chosen
model. The program opens on the Overview tab, and the title "JBG Automatic
classification" leads there.
Choose the language with SV/EN at the top right.

Buttons that perform an action are green when they can be used and red,
dimmed, while there is nothing to do yet, for example **Save** before
anything has changed. Hold the pointer over a red button to see why. Orange
buttons can be used but cannot be undone, such as **Delete**. On long
pages, the page's main button is at both the top and the bottom.

## Overview

At the top, all your projects: training runs, rows processed, models
compared and models in use, each with how many are in the open project; runs
per week (succeeded and failed) and rows processed per project, with the open
project highlighted. Rows processed and models compared are recorded when a
run finishes, so runs from before this version count as zero.

Below, the open project: the active training dataset, the chosen
configuration, the latest runs and the project's models, each linking to the
tab where it is changed; model quality per training run (the configuration's
metric) with the average of the last three; rows processed per week; and the
latest runs, linking to their results. Without an open project only the top
part is shown.

## Projects

All work belongs to a project. Enter a name and a source (SQL or CSV) and
choose **Create project**. The source cannot be changed afterwards. Select
the project in the list and choose **Open project** to work with it. The
cross by the project name in the line below the title closes the project.

**Delete the project…** deletes the project with everything in it:
datasets, configurations, runs with their results and predictions, and
models. Type the project's name to confirm; the **Delete** button turns
orange when the name is right. Tables in SQL Server are not touched.

## Dataset

A project can have several datasets. Each dataset has a role: Training,
Prediction or Mixed.

- **CSV projects**: choose a file (at most 25 MB, with a header row; the
  delimiter is detected automatically), enter a name and a role and choose
  **Upload**.
- **SQL projects**: sign in with a user name and password or with Windows
  authentication. Choose a catalog and a role, **Show tables**, choose a
  table, enter a name and choose **Register**. The sign-in is kept only in
  the server's memory; after a server restart, sign in again.

The name is filled in with the file's name without ".csv", or the table's name
without the schema. It can be changed, and it follows the chosen file or table
until you type a name of your own.

Choose **Activate for training** on the dataset the model is to be trained
on. A training or mixed dataset can switch to the other role with **Change
role to …**; its column roles and validation are kept. Training uses only
rows with a class, and a mixed dataset can also be predicted on the
Prediction tab. Prediction datasets cannot switch role. Below the dataset are the views Preview, Profile, Classes and Column
roles.

The **Rename the dataset** panel below the list gives the selected dataset a
new name with **Rename**. Only the name changes: the file or table, the column
roles and the runs stay, and the runs show the new name. The name must not
already exist in the project, whatever the case.

**Delete the dataset…** deletes the dataset with its column roles, every
version of its CSV file (corrected ones included), the training runs on it,
the models trained on it and the predictions made on it or with those
models. Configurations stay: they are not tied to a dataset.

### Column roles

The column roles belong to the training dataset and apply to every run with
it. Exactly one column must be the ID column and exactly one the class
column, and at least one column must be a feature: a numeric feature, a text
feature or a categorical feature. Ignored columns are not used.

In SQL datasets the ID column must be a whole-number column (int, bigint,
smallint or tinyint), not for example uniqueidentifier or text. Otherwise
**Treated as** shows a warning, validation fails the ID column and a run does
not start. In CSV datasets the ID column can hold anything.

A date column can have the role **Date feature**. It then becomes the year
(a number), month and weekday (points on a circle, so that December lies
next to January) and a mark for a missing date. Dates are never suggested
automatically: a date column is suggested as ignored, and **Treated as**
shows that it can be a date feature. Dates must be in the format YYYY-MM-DD,
optionally with a time; in SQL tables the types date, datetime, datetime2 and
smalldatetime count. Keep in mind that the year only describes the period
the model was trained on; a new year is a value it has not seen.

At most one column can be the **Group column**, for example a person's
identity. It keeps its rows together when data is split, so that one group
is not in both training and test, but it is not used as a feature. It is
needed when the configuration keeps groups apart. Prediction datasets must
also contain the group column.

If the dataset has no saved column roles, the form is filled in with
suggestions: the first filled-in column with a different value on every row
becomes the ID column, numbers become numeric features, text with at most as
many distinct values as the categorical limit becomes categorical features
and other text text features. Empty and single-valued columns are ignored,
as are, for example, date columns in SQL tables. The class column is not
suggested: choose it in the form, or show a column's distribution on the
Classes view, and it becomes the class column in the suggestion. The
suggestion is not kept until you choose **Save column roles**.

**Categorical limit** (default 30, allowed 2–1000): text columns with at most
this many distinct values are treated as categories, other text columns as
free text. Categorical features are always categorised. The column "Treated
as" shows the outcome.

Save with **Save column roles**, then validate the dataset again with
**Validate dataset** at the bottom.

If the project already has a dataset with the same columns, choose it under
**Copy column roles from** and **Fill in**. The roles are filled in but not
kept until you save; columns that are missing or not numbers are pointed
out. A configuration can be used with every dataset in the project.

## Configuration

A configuration holds the machine learning settings. **Create
configuration** starts with the default settings.

The sections come in the order the steps run: Run type, Text processing,
Feature selection, Data split, Scaling, Oversampling, Undersampling,
Dimensionality reduction, Algorithms, Decision, Evaluation, Dark Numbers
and, in SQL projects, Predictions, last Advanced. Scaling, sampling,
dimensionality reduction and the algorithm are tried together in
cross-validation. Every section is closed when the page opens; click a
section's title to open or close it. Sections that were open when you saved
stay open after saving. Less common settings are under **Advanced settings**
in each section.

**Algorithms**: the algorithms are listed in groups (linear, non-linear,
neighbours, naive Bayes, trees, ensembles, imbalanced data, robust to
mislabelling, neural networks, special), sorted by name within each group.
**select all** and **clear** act on one group.

**Feature selection**: the variables a model uses are chosen with the column
roles on the Dataset tab. A column with the role Ignored is not used. The
settings in this section are used by the feature investigation (see
Training). Quick, Standard and Extended set the size of the search, Custom
uses the values in the section.

On the left, below the list, **Pipeline** shows the steps of the open
configuration in the order they run. A green step is used, a purple one
compares several alternatives and a dashed one is not used. The steps tried
together in cross-validation are framed, with the number of combinations.
Click a step to open its section. The picture shows the saved version.

In **Data split**, choose whether groups are kept apart in cross-validation
or in the holdout split. The group column is not set here but as a column
role on the Dataset tab; the section shows which column is used. Keeping
groups apart in the holdout split needs two classes. In **Oversampling** and **Undersampling**, tick the
methods to try; with nothing ticked, no sampling is used.

In **Dark Numbers**, the **Target class** is chosen among the classes of the
active training dataset's class column, or **All classes**. The classes are
read when the section is opened (SQL projects need a sign-in). Below the
fields is the formula of the chosen method and alpha, with the target class
and the fallback; it follows your choices at once, and alpha "Separated" can
only be chosen with the method "Linear".

- The **All** box in a list ticks every choice. It is also ticked when the
  last choice is ticked, and it is unticked when a choice is unticked.
- **Save configuration** creates a new version; earlier versions are kept. A
  new configuration is version 0, so the first change makes version 1. The list
  shows the last created or changed configuration first.
- The **Rename the configuration** panel below the list gives the selected
  configuration a new name without creating a new version. The runs made with
  it show the new name, and it moves to the top of the list. Models keep the
  name they were given when they were trained.
- **Choose for runs** makes the configuration the one used for training.
  It is red when the configuration is already chosen.
- **Delete the configuration…** deletes it with every version, the training
  runs made with it, their models and the predictions made with those
  models (see Deleting below).
- CSV runs only train. New configurations in CSV projects therefore have
  "Predict unlabelled rows" unticked.

## Training

The list **Before the run** shows whether everything needed is there: an
active training dataset with column roles, a chosen configuration and, for
SQL, a sign-in. For a point that is not met, **Put right** leads to where it
is fixed. **Start training** starts the run with the active dataset
and the chosen configuration.

While a run of the project is queued or running, **Start training** and
**Investigate features** (and **Start prediction** on the Prediction tab)
are unavailable until it has finished.

A finished run can be deleted with **Delete the run…** (also on the
Prediction and Results tabs).

**Investigate features** starts a feature investigation with the same
dataset and configuration. It searches the training part for a smaller set of
variables that predicts as well as or better than all of them, using nested
cross-validation, and saves no model. With more than two classes, the Dark
Numbers target class (or else the smallest class) is investigated against the
other classes. The investigation cannot keep groups apart yet, so it is not
offered for a dataset with a group column. When it has finished, the run
shows the recommendation: how many variables, and the MCC with them and with
every variable.

The progress updates itself. While the models are trained and compared, a
thinner bar shows how many algorithm combinations are done, for example
"12 of 40". Then it shows the final training of the winning pipeline. With
a parameter search the bar moves with the time against an estimate, for example
"2 min of about 4 min", and waits just before the end until the search is done.
The estimate grows if the search takes longer. The run continues even if you
close the browser, and it can be stopped with **Cancel the run**. **Show log** shows
the run's log.

**Cancel the run** asks the run to stop: it stops after the step it is
working on, such as the algorithm combination being tried. A long step can
take a while. Once you have cancelled, **Stop now** ends the run at once; the
step in progress is lost, which does not matter for a cancelled run. If the
program on the server is stopped or ends unexpectedly, its runs are marked
interrupted: at once when the server notices, otherwise after five minutes.

If the configuration also predicts rows without a class but the training
dataset has no such rows, the run only trains and skips the prediction; the
log says so.

When the run has finished, the evaluation on the holdout data, the
confusion matrix and the most important features are shown.

## Results

The project's finished training runs. For a selected run there are the
views Overview, Model comparison, Mispredictions, Feature importance and
Dark Numbers. Class names and row values are shown only to the person who
started the run. Older runs may lack some details.

A finished **feature investigation** shows its recommendation: the
recommended variables and those left out, and the MCC with them and with
every variable (nested cross-validation on the training part). **Use the
recommendation** opens the dataset's column roles with the left-out columns
set to Ignored (a date column only if all its parts were left out); nothing
is saved until **Save column roles**. It cannot be used if the column roles
have changed since the investigation, or if the recommendation keeps every
variable.

**Dark Numbers** shows, when the configuration estimates Dark Numbers, the
estimated share of hidden cases for each target class. Four estimates are
made: with the final model and with the cross-trained model on all data, a
combined one, and with the cross-trained model on the test data. They are
shown sorted from the lowest to the highest, each labelled with its model
variant, and together form an interval with subintervals. Below are the
calculations and the confusion matrices.

An estimate can be **Undefined**. That happens when the part of the data it
is made on lacks rows of the target class or of the other classes, or when
the correction factor c could not be estimated or lies outside 1 to the upper
bound set in the configuration (10 by default). It means that the pipeline or
the dataset is ill-suited to estimating Dark Numbers for that target class.

A warning says when the model learns some of the deliberately wrong labels by
heart: c is above the warning level set in the configuration (2 by default),
or the model fits its training rows clearly better than rows it has not seen.
c corrects for this, but with uncertainty, and a pipeline that learns less by
heart gives a more reliable Dark Number.

### Dark Numbers in detail (JBG 1.3)

**What is estimated.** For a target class T, the Dark Number D estimates the
hidden share: of the rows registered as another class, the share that really
belong to T. Multiplied by the number of rows registered as another class, it
gives the estimated number of hidden cases. It is computed separately for
each target class, the target class against all the others.

**The equation** (linear method, separated alpha, the default):
`D = min(c · α_FP · (1 − TN_r) · (1 + α_FN · (1 − TP_r)), 1)`

- `1 − TN_r = FP / (FP + TN)`: the share of the rows registered as another
  class that the model predicts as T. These are the candidates for hidden
  cases. Without the other factors, `min((1 − TN_r) · (2 − TP_r), 1)` is the
  basic estimate of the hidden share.
- `1 − TP_r = FN / (TP + FN)`: the share of T's own rows that the model
  misses. A model that misses known cases also misses hidden ones, so the
  candidates are scaled up by 1 plus this share. It is a cautious version of
  dividing by TP_r: equal for good models, more restrained for weak ones.
- `α_FP`: the mean probability of T on the false positives. Not every false
  positive is a hidden case, some are plain model errors. A confident false
  positive counts almost fully, an uncertain one little (soft counting).
- `α_FN`: the mean probability of not being T on the false negatives. It
  weighs the misses only, so with no misses the scaling factor is 1.
- `c`: the correction factor for overtraining, from the flip test. A share of
  T's rows is deliberately given another class (20 % by default, spread over
  the other classes by their size) and a copy of the model is trained, in 4
  parts and 2 repeats (by default). The parts are the same on every computer,
  whatever its number of processor cores, so c is the same. Each copy is
  asked about two kinds of
  rows: the relabelled rows it was trained on (it recognises a share `r_in` of
  them as T) and T's rows in the part it has not seen (a share `r_unseen`).
  `c = r_unseen / r_in`, at least 1. A model that learns wrong labels by heart
  recognises far fewer of the rows it was trained on, so `c` is large; a model
  that does not overtrain recognises both kinds about equally, so `c` is about
  1. The model's ordinary misses affect both shares alike and cancel in the
  ratio; they are counted once, by the second factor. Since 1.3 (2026-11-19):
  `c` was `1 / r_in`, which also contained the ordinary misses and so counted
  them twice. The calculation table shows `c` with a 90 % interval and a
  quality, and the two factors it is made of.
- The result is capped at 100 %. A value above it means that the estimate
  has broken down for that target class, and the view says so.

**Two readings.** A switch at the top of the Dark Numbers view shows either
the share among the other classes (as above), or the growth of the target
class: how much it would grow if the hidden cases were added,
`g = D · N_rest / N_target`, where N_rest and N_target are the rows
registered as another class and as the target class in the same estimate.
The growth is shown as a percentage and a factor, with the estimated number
of hidden cases, the registered cases, and the share of all real cases that
were missing from the register, `g / (1 + g)`. Like D, it assumes that the
rows registered as the target class belong to it. With a rare target class,
small changes in D give large changes in the growth.

**The four estimates** are made with the cross-trained model on the test
part, with the cross-trained model on all data, with the final model on all
data, and combined. The test part is new to the model, so `c` is not used
there. The other three include rows the model was trained on and are
corrected with `c`. The four model variants are shown sorted from the lowest
to the highest and together form an interval with subintervals. There is no
expected order between them.

**Undefined estimates.** An estimate is undefined when the part of the data
it is made on lacks rows of T or of the other classes, or when `c` could not
be estimated or lies outside 1 to the upper bound (10 by default). That means
the pipeline or the dataset is ill-suited to the problem for that target
class. With no false positives the Dark Number is 0 whatever `c` is.

**Warnings.** When `c` is above the warning level (2 by default), the model
learns some of the deliberately wrong labels by heart; `c` corrects for it,
with uncertainty. The calculation table says so for each estimate.

**Settings.** The configuration's Dark Numbers section sets, besides the
flip fraction and the sampling, the repeats in the flip test (2 by default;
each adds 4 model fits and narrows `c`'s interval, useful with a rare target
class), the upper bound for `c` (10) and the warning level (2). The values
used are shown with the equation and stored with the result.

**Other forms.** Without alpha, D uses `(2 − TP_r)` without weights. The
single-alpha and non-linear forms are kept as they were, with the same cap and
the same use of `c`.

**Sampling in the correction test.** The configuration's Dark Numbers
section chooses how the test behind c samples the data. "As the pipeline"
(the default) uses the winning pipeline's own over- and undersampling, as
before. When the target class is the majority class and the pipeline uses
SMOTE, the deliberately relabelled rows become the class SMOTE grows, which
can make c too high; the Dark Numbers view then warns. "None", "SMOTE",
"SMOTE from unflipped rows" (synthetic rows only from rows that were not
relabelled) and "Undersampling (1 : 1)" replace the pipeline's sampling in
the test only. Ordinary training is not affected.

**c's parts.** The calculation table shows, beside c, the two factors it is
made of: "c in the training rows" (`1 / r_in`, the correction factor before
1.3) and "c in the unseen part" (`1 / r_unseen`), and c's 90 % interval and
quality (reliable, uncertain, not estimable). An uncertain c is used, but the
view says so. The validation study (in `docs/dark_numbers/`) showed that this
c brings the estimates on all data as close to the truth as the test-part
estimate, where the earlier c roughly doubled the error.

**Version and settings.** The equation section names the method version and
the settings used (flip fraction, folds and repeats, the bounds on c, the
memorisation rule, the random seed). Runs made before version 1.2 have no
such record: their values are shown as they were saved, with a note.

**What comes next.** The measurement on rows the model has not been trained
on and the interval for `c`, planned earlier for version 2, are in place since
1.3 (see c's parts above). Still in the plan are methods that estimate the
hidden share directly, with intervals. The plan is in `docs/dark_numbers/` in
the repository.

In **Mispredictions** of an SQL run you can correct classes that are wrong
in the source data. Choose the **Right class** for the rows, then **Review
the corrections**. A page shows the changes, and only when you choose
**Write the corrections** are they written to the source table with your SQL
sign-in, all at once or none. The sign-in must be allowed to change the
table. Corrected rows are marked, and the corrections are listed below the
table; **Undo** writes the old class back. The next training uses the
corrected classes.

For a CSV run it works the same way, but the corrections are saved in a new
version of the dataset's file, which every later run reads; the uploaded file
is kept. The dataset needs validating again. **Download CSV** on the Dataset
tab downloads the file with the corrected classes.

In **Dark Numbers** each estimate is also shown in percent, with a bar on
the target class's scale, and below the table the range from the smallest
to the largest estimate.

Wide tables have a scrollbar both below and above the table.

## Models

The models the training runs have created, with where they came from and
their key figures, and the model's remaining runs. **Choose model** makes an
available model the one used for prediction. **Delete the model…** deletes
it with its files and the prediction runs made with it.

## Prediction

Prediction uses the model chosen on the Models tab.

- **SQL projects**: predict the training dataset's rows without a class, or
  a registered prediction dataset that is compatible with the training
  dataset. The predictions are written to the prediction table in SQL
  Server. A table without a class column is predicted in full.
- **CSV projects**: predict the training dataset's rows without a class, or
  a prediction (or mixed) dataset with the same columns. The rows without a
  class are predicted; a file without a class column is predicted in full.
  If the file does not fit the model, or every row already has a class, the
  tab says so before anything starts.

When the run has finished, the predictions are shown page by page, and they
can be downloaded as a file with **Download the predictions**. In CSV
projects, **Download with the original columns** downloads the predictions
together with all columns of the predicted rows, from the file the prediction
read.

## Run History

Available in a later version.

## Good to know

- Logs and predictions may contain values from your data and are shown only
  to the person who started the run.
- Every run keeps its results in a folder of its own on the server.
- **Deleting**: what owns something takes it with it. A run takes its log
  and result files; a model its files and its prediction runs; a
  configuration its versions, its training runs and their models; a
  dataset its file versions, the runs on it and the models trained on it; a
  project everything in it. CSV file versions that nothing uses any more are
  cleaned up when a dataset is deleted. A page
  first lists exactly what is deleted and what stays; **Delete** (orange)
  carries it out and cannot be undone. Nothing is deleted while a run that
  would go is queued or running. When a training run is deleted but its
  model is kept, only the run's settings are kept for the model, hidden.
  Tables in SQL Server are never changed: predictions and corrections
  already written stay.
- This tab shows the program's version.
