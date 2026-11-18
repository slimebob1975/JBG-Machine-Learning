"""299y, DN-02 (settled 2026-11-16): a separate sampling policy for the flip
test behind the Dark Number correction factor. PIPELINE (default) keeps the
winning pipeline's own sampling as before, with a warning when its
oversampling meets a majority target (the flipped rows become the minority
SMOTE grows). NONE, SMOTE, CLEAN_SMOTE (synthetic rows only from unflipped
rows; too few: NONE for that fold, flagged) and UNDER (1 : 1) switch the
pipeline's samplers off and resample the flipped training part themselves."""
import warnings

import numpy as np
import pytest
from imblearn.over_sampling import SMOTE
from imblearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression

from JBGDarkNumberCorrectionFactor import DarkNumberCorrectionFactorEstimator
from JBGDarkNumberSampling import (DEFAULT_POLICY, POLICIES, contamination_risk, has_oversampler,
                                   resample, without_samplers)


def _pipe():
    return Pipeline([("SME", SMOTE(random_state=0)), ("NUG", "passthrough"),
                     ("LRN", LogisticRegression(max_iter=300))])


def test_the_policies():
    assert POLICIES == ("PIPELINE", "NONE", "SMOTE", "CLEAN_SMOTE", "UNDER")
    assert DEFAULT_POLICY == "PIPELINE"


def test_the_pipelines_samplers_are_switched_off_in_the_copy():
    pipe = _pipe()
    assert has_oversampler(pipe)
    copy = without_samplers(pipe)
    assert copy.named_steps["SME"] == "passthrough" and not has_oversampler(copy)
    assert isinstance(copy.named_steps["LRN"], LogisticRegression)
    assert not has_oversampler(LogisticRegression())


def test_the_contamination_risk_needs_the_default_smote_and_a_majority_target():
    y = np.array(["Ja"] * 86 + ["Nej"] * 14)
    assert contamination_risk(_pipe(), y, "Ja", "PIPELINE") is True
    assert contamination_risk(_pipe(), y, "Nej", "PIPELINE") is False      # minority target
    assert contamination_risk(_pipe(), y, "Ja", "CLEAN_SMOTE") is False    # another policy
    assert contamination_risk(LogisticRegression(), y, "Ja", "PIPELINE") is False


def _data():
    rng = np.random.default_rng(0)
    y = np.array(["a"] * 80 + ["b"] * 20)
    X = rng.normal(size=(100, 2))
    flip = np.zeros(100, dtype=bool)
    flip[[0, 1, 2]] = True                          # three "a" rows flipped to "b"
    y = y.copy()
    y[[0, 1, 2]] = "b"
    X[[0, 1, 2]] = 1000.0                           # far away, to see who seeds new rows
    return X, y, flip


def test_none_smote_and_under():
    X, y, flip = _data()
    same_X, same_y, info = resample("NONE", X, y, flip, 1)
    assert same_X is X and info == {"synthetic": 0, "fallback": False}
    X_s, y_s, info = resample("SMOTE", X, y, flip, 1)
    assert (y_s == "a").sum() == (y_s == "b").sum() == 77 and info["synthetic"] == 54
    X_u, y_u, info = resample("UNDER", X, y, flip, 1)
    assert (y_u == "a").sum() == (y_u == "b").sum() == 23 and info["synthetic"] == 0


def test_clean_smote_never_grows_from_flipped_rows():
    X, y, flip = _data()
    X_c, y_c, info = resample("CLEAN_SMOTE", X, y, flip, 1)
    assert info == {"synthetic": 54, "fallback": False}
    assert (y_c == "a").sum() == (y_c == "b").sum() == 77
    synthetic = X_c[100:]
    assert np.abs(synthetic).max() < 100             # none between flipped rows (at 1000)
    X_s, _, _ = resample("SMOTE", X, y, flip, 1)
    assert np.abs(X_s[100:]).max() > 100             # ordinary SMOTE does use them


def test_clean_smote_falls_back_with_too_few_clean_rows():
    X, y, flip = _data()
    flip[:] = False
    flip[y == "b"] = True                            # no clean "b" rows at all
    X_c, y_c, info = resample("CLEAN_SMOTE", X, y, flip, 1)
    assert info == {"synthetic": 0, "fallback": True} and X_c is X


def test_the_estimator_records_its_sampling_and_the_default_is_unchanged():
    rng = np.random.default_rng(3)
    y = np.where(rng.random(600) < 0.85, "Ja", "Nej")
    X = np.c_[rng.normal(size=600) + (y == "Ja") * 1.2, rng.normal(size=600)]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fitted = {policy: DarkNumberCorrectionFactorEstimator(
            estimator=_pipe(), flip_fraction=0.2, n_splits=4, n_repeats=2, n_jobs=1,
            random_state=42, positive_class="Ja", sample_size=1.0,
            sampling_policy=policy).fit(X, y) for policy in POLICIES}
    assert fitted["PIPELINE"].sampling_info_ == {"policy": "PIPELINE", "synthetic_rows": 0,
                                                 "fallback_folds": 0}
    assert fitted["SMOTE"].sampling_info_["synthetic_rows"] > 0
    assert fitted["NONE"].correction_factor_ < fitted["PIPELINE"].correction_factor_
    assert fitted["CLEAN_SMOTE"].correction_factor_ <= fitted["SMOTE"].correction_factor_


def test_the_configuration_field():
    from Config import Config
    from JBGConfigSchema import configuration_schema
    from JBGConfigurationService import _server_template
    from JBGWebUI import translator
    assert Config.LATER_KEYS["mode"]["dark_number_sampling_policy"] == "PIPELINE"
    assert Config.Mode().dark_number_sampling_policy == "PIPELINE"
    with pytest.raises(ValueError):
        Config.Mode(dark_number_sampling_policy="LOTS").validate()
    schema = configuration_schema("csv", translator("sv"), _server_template())
    field = next(f for f in schema["fields"] if f["key"] == "mode.dark_number_sampling_policy")
    assert field["group"] == "dark_numbers" and field["label"] == "Sampling i korrektionstestet"
    assert [o["value"] for o in field["options"]] == list(POLICIES)
    assert field["options"][0]["label"] == "Som pipelinen (som tidigare)"


def test_the_results_tab_shows_the_policy_and_the_risk(tmp_path):
    import json
    import pandas as pd
    from types import SimpleNamespace
    from JBGDarkNumberRecord import build
    from test_revision_299b_csv_reclassification import _client, _setting
    from test_revision_299x_dark_number_record import CALCULATIONS, CONFIG
    frame = pd.DataFrame([{"Model type": "D_cv_full - M", "type": "separated_alpha",
                           "target": "a", "corr": 2.0, "corr_model": "M",
                           "corr_source": "direct", "dark_number": 0.1}])
    record = build(CONFIG, frame, {"random_state": 42, "sampling": {
        ("M", "a"): {"policy": "PIPELINE", "synthetic_rows": 0, "fallback_folds": 0,
                     "contamination_risk": True}}})
    assert record["parameters"]["sampling_policy"] == "PIPELINE"
    assert record["estimates"][0]["sampling"]["contamination_risk"] is True
    with _client(tmp_path) as client:
        s = _setting(client, tmp_path)
        csvs = s.folder / "output" / "csvs"
        (csvs / "dark_numbers_r__train.csv").write_text(CALCULATIONS, encoding="utf-8")
        (csvs / "dark_numbers_r__train.json").write_text(json.dumps(record), encoding="utf-8")
        page = client.get(f"/ui/results?run={s.run}&view=dark_numbers").text
    assert "sampling i korrektionstestet: Som pipelinen (som tidigare)" in page
    assert "Målklassen är majoritetsklassen" in page and "för höga för: a." in page


def test_the_template_tolerates_missing_sampling_values():
    """299y2: a server started before the patch renders the new template with
    the old context; the settings line must not crash."""
    from JBGWebUI import WEB
    template = (WEB / "templates" / "results.html").read_text(encoding="utf-8")
    assert "(sampling_labels if sampling_labels is defined else {})" in template
    assert "dark_sampling_risks is defined and dark_sampling_risks" in template
