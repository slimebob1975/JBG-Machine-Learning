"""300w (2026-11-24): Average Precision on probabilities with any class labels,
and the Dark Number presented as an estimate (decided 2026-11-24)."""
import json
import pickle
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest
from sklearn.datasets import make_classification
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.svm import LinearSVC

from JBGMeta import ScoreMetric
from JBGScorers import AveragePrecisionScorer, smallest_class

ROOT = Path(__file__).resolve().parent.parent
AP = ("average_precision_micro", "average_precision_macro", "average_precision_weighted")


def _binary():
    X, y = make_classification(600, 6, n_informative=3, weights=[0.85], random_state=1)
    return X, y, np.where(y == 1, "Inkorrekt", "Korrekt")


# --- Average Precision ------------------------------------------------------------------

@pytest.mark.parametrize("name", AP)
def test_text_and_number_classes_score_alike(name):
    X, numbers, text = _binary()
    scorer = ScoreMetric[name].get_parametrized_scorer()
    assert isinstance(scorer, AveragePrecisionScorer)
    scores = [cross_val_score(LogisticRegression(max_iter=300), X, labels, cv=StratifiedKFold(3),
                              scoring=scorer, error_score="raise").mean() for labels in (text, numbers)]
    assert scores[0] == pytest.approx(scores[1])


def test_it_scores_the_probabilities_of_the_smallest_class():
    X, y, text = _binary()
    model = LogisticRegression(max_iter=300).fit(X[:400], text[:400])
    expected = average_precision_score(text[400:] == "Inkorrekt",
                                       model.predict_proba(X[400:])[:, list(model.classes_).index("Inkorrekt")])
    assert smallest_class(text) == "Inkorrekt"
    assert AveragePrecisionScorer("macro")(model, X[400:], text[400:]) == pytest.approx(expected)
    flipped = AveragePrecisionScorer("macro", positive_class="Korrekt")(model, X[400:], text[400:])
    assert flipped != pytest.approx(expected)                       # the positive class matters


def test_models_without_probabilities_use_the_decision_values():
    X, _, text = _binary()
    model = LinearSVC().fit(X[:400], text[:400])
    score = AveragePrecisionScorer("macro")(model, X[400:], text[400:])
    expected = average_precision_score(text[400:] == "Inkorrekt",
                                       -model.decision_function(X[400:])
                                       if model.classes_[1] != "Inkorrekt" else model.decision_function(X[400:]))
    assert score == pytest.approx(expected)


def test_more_than_two_classes_average_over_each_class():
    X, y = make_classification(600, 6, n_informative=4, n_classes=3, random_state=2)
    text = np.array(["a", "b", "c"])[y]
    for name in AP:
        score = cross_val_score(LogisticRegression(max_iter=300), X, text, cv=3,
                                scoring=ScoreMetric[name].get_parametrized_scorer(),
                                error_score="raise").mean()
        assert 0 < score <= 1


def test_the_scorer_pickles_and_the_stored_values_stay():
    scorer = ScoreMetric.average_precision_weighted.get_parametrized_scorer().for_positive_class("x")
    again = pickle.loads(pickle.dumps(scorer))
    assert (again.average, again.positive_class) == ("weighted", "x")
    assert ScoreMetric.average_precision_macro.value["kwargs"] == {"average": "macro"}
    assert pickle.loads(pickle.dumps(ScoreMetric.average_precision_micro)) is ScoreMetric.average_precision_micro


def _resolver(scoring, target=""):
    from JBGHandler import ModelHandler
    mode = SimpleNamespace(scoring=scoring, dark_number_target=target)
    config = SimpleNamespace(mode=mode, get_scoring_mechanism=lambda: scoring.get_mechanism())
    return ModelHandler(SimpleNamespace(config=config, logger=Mock(), STANDARD_DESIRED_N_JOBS=1))


def test_the_positive_class_is_the_dark_numbers_target_or_the_smallest():
    labels = pd.Series(["Korrekt"] * 9 + ["Inkorrekt"])
    chosen = _resolver(ScoreMetric.average_precision_macro, "Korrekt") \
        ._resolve_scoring_mechanism_for_target(labels)
    assert chosen.positive_class == "Korrekt"
    default = _resolver(ScoreMetric.average_precision_macro)._resolve_scoring_mechanism_for_target(labels)
    assert default.positive_class == "Inkorrekt"
    absent = _resolver(ScoreMetric.average_precision_macro, "Saknas") \
        ._resolve_scoring_mechanism_for_target(labels)
    assert absent.positive_class == "Inkorrekt"
    three = _resolver(ScoreMetric.average_precision_macro)._resolve_scoring_mechanism_for_target(
        pd.Series(["a", "b", "c"]))
    assert three.positive_class is None
    assert _resolver(ScoreMetric.mcc)._resolve_scoring_mechanism_for_target(labels) is not None


# --- The Dark Number as an estimate -----------------------------------------------------

NOTE_EN = ("The Dark Number is an estimate, not a statistically proven share. It rests on the "
           "model's errors and on assumptions that cannot be tested with the data at hand.")
NOTE_SV = ("Mörkertalet är en skattning, inte en statistiskt säkerställd andel. Den bygger på "
           "modellens fel och på antaganden som inte kan prövas med de egna data.")


def test_the_view_says_it_is_an_estimate(tmp_path):
    from JBGDarkNumberRecord import build
    from test_revision_299b_csv_reclassification import _client, _setting
    from test_revision_299x_dark_number_record import CALCULATIONS, CONFIG
    record = build(CONFIG, pd.DataFrame(), {"random_state": 42})
    with _client(tmp_path) as client:
        s = _setting(client, tmp_path)
        csvs = s.folder / "output" / "csvs"
        (csvs / "dark_numbers_r__train.csv").write_text(CALCULATIONS, encoding="utf-8")
        (csvs / "dark_numbers_r__train.json").write_text(json.dumps(record), encoding="utf-8")
        share = client.get(f"/ui/results?run={s.run}&view=dark_numbers").text
        growth = client.get(f"/ui/results?run={s.run}&view=dark_numbers&dark_view=growth").text
        client.post("/ui/language", data={"language": "en", "next": "/ui/results"},
                    follow_redirects=False)
        english = client.get(f"/ui/results?run={s.run}&view=dark_numbers").text
    for page in (share, growth):
        assert f'<p class="message note">{NOTE_SV}' in page
        assert "<th class=\"num\">Skattat mörkertal</th>" in page
    assert f'<p class="message note">{NOTE_EN.replace("\'", "&#39;")}' in english   # escaped
    assert '<th class="num">Estimated Dark Number</th>' in english


def test_the_guides_say_it_is_an_estimate():
    sv = (ROOT / "docs" / "user_guide.sv.md").read_text(encoding="utf-8")
    en = (ROOT / "docs" / "user_guide.en.md").read_text(encoding="utf-8")
    assert "Mörkertalet är en skattning, inte en statistiskt säkerställd andel." in sv
    assert "The Dark Number is an estimate, not a statistically proven share." in en


def test_the_python_version_is_recorded():
    assert "Python 3.13.7" in (ROOT / "docs" / "dependencies.md").read_text(encoding="utf-8")
