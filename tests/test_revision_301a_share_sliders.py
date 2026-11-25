"""301a (specified 2026-11-24): the share sliders for over- and undersampling.

The oversampling slider sets the smallest class's share after sampling, raised
towards 50 %. The undersampling slider sets the largest class's share, lowered
towards 50 %. Both start at the class's current share in the active training
dataset. Ticked sampling with an untouched slider stops the save, with "use the
standard values" (the next class's share, never past 50 %) as the way on. One
value applies to every chosen method that can use it. The undersampling presets
R02-R20 are removed, and stored configurations that use them are converted."""
import json
from collections import Counter
from pathlib import Path

import numpy as np
import pytest

from JBGSampling import (UNDERSAMPLING_PRESETS, class_shares, convert_undersampling_presets,
                         share_counts, share_notes, share_unchanged)

ROOT = Path(__file__).resolve().parent.parent


# --- The share ---------------------------------------------------------------------------

def test_the_share_sets_the_smallest_or_largest_class():
    y = np.array([0] * 90 + [1] * 10)
    over = share_counts(y, 30, "over")
    assert over == {1: 39} and 39 / (90 + 39) == pytest.approx(0.30, abs=0.005)
    under = share_counts(y, 60, "under")
    assert under == {0: 15} and 15 / (15 + 10) == pytest.approx(0.60)
    assert share_counts(y, 5, "over") == {1: 10}           # already beyond: unchanged
    assert share_counts(y, 95, "under") == {0: 90}
    three = np.array(["a"] * 60 + ["b"] * 30 + ["c"] * 10)
    assert share_counts(three, 20, "over") == {"c": 22}     # 22 / (90 + 22) = 19.6 %
    assert share_counts(three, 50, "under") == {"a": 40}    # 40 / (40 + 40) = 50 %
    with pytest.raises(ValueError):
        share_counts(y, 30, "sideways")


def test_the_current_shares_and_the_standard_values():
    two = class_shares(Counter([0] * 80 + [1] * 20))
    assert two == {"smallest": 20.0, "largest": 80.0, "standard_over": 50.0, "standard_under": 50.0}
    three = class_shares({"a": 60, "b": 30, "c": 10})
    assert (three["standard_over"], three["standard_under"]) == (30.0, 50.0)
    four = class_shares({"a": 40, "b": 35, "c": 15, "d": 10})
    assert (four["standard_over"], four["standard_under"]) == (15.0, 50.0)
    assert class_shares({"a": 5}) == {}


def test_an_untouched_slider_changes_nothing():
    shares = class_shares({"a": 80, "b": 20})
    assert share_unchanged(None, shares, "over") and share_unchanged(None, shares, "under")
    assert share_unchanged(20.0, shares, "over") and not share_unchanged(30.0, shares, "over")
    assert share_unchanged(80.0, shares, "under") and not share_unchanged(70.0, shares, "under")


def test_a_pipeline_samples_to_the_share():
    from functools import partial
    from imblearn.over_sampling import SMOTE
    from imblearn.under_sampling import RandomUnderSampler
    from sklearn.datasets import make_classification
    X, y = make_classification(400, 5, weights=[0.9], random_state=0)
    _, over = SMOTE(sampling_strategy=partial(share_counts, share=30.0, role="over"),
                    random_state=0).fit_resample(X, y)
    assert Counter(over)[1] / len(over) == pytest.approx(0.30, abs=0.01)
    _, under = RandomUnderSampler(sampling_strategy=partial(share_counts, share=60.0, role="under"),
                                  random_state=0).fit_resample(X, y)
    assert Counter(under)[0] / len(under) == pytest.approx(0.60, abs=0.01)


def test_the_builder_sets_the_share_only_where_it_applies():
    from sklearn.preprocessing import FunctionTransformer, StandardScaler
    from sklearn.linear_model import LogisticRegression
    from JBGMeta import Algorithm, Oversampling, Preprocess, Reduction, Undersampling
    from JBGPipelineConstruction import build_model_pipeline
    reducer = FunctionTransformer(lambda X: X)

    def build(over, under, **shares):
        return build_model_pipeline(Reduction.NOR, reducer, Algorithm.LRN, LogisticRegression(),
                                    Preprocess.STA, StandardScaler(), over, under, 5, **shares)
    pipe = build(Oversampling.SME, Undersampling.RND, oversampling_share=30.0,
                 undersampling_share=60.0)
    steps = dict(pipe.steps)
    over, under = steps["SME"].sampling_strategy, steps["UNDER_RND" if "UNDER_RND" in steps else "RND"].sampling_strategy
    assert (over.keywords, under.keywords) == ({"share": 30.0, "role": "over"},
                                               {"share": 60.0, "role": "under"})
    cleaning = dict(build(Oversampling.NOG, Undersampling.TKL, undersampling_share=60.0).steps)
    assert cleaning["TKL"].sampling_strategy == "auto"                 # takes no share
    balanced = dict(build(Oversampling.SME, Undersampling.NUG).steps)
    assert balanced["SME"].sampling_strategy == "auto"                 # no share: as before


def test_the_run_log_notes():
    from Config import Config
    from JBGMeta import Oversampling, Undersampling
    labels = ["a"] * 80 + ["b"] * 20
    reached = Config.Mode(oversamplers=["SME"], oversampling_share=15.0)
    assert any("already at 20.0 %" in note for note in share_notes(reached, labels))
    cleaning = Config.Mode(undersamplers=["RND", "TKL"], undersampling_share=60.0)
    assert any("take no share" in note and "TKL" in note for note in share_notes(cleaning, labels))
    assert share_notes(Config.Mode(oversamplers=["SME"], oversampling_share=30.0), labels) == []


# --- The presets -------------------------------------------------------------------------

def test_the_presets_are_converted():
    assert UNDERSAMPLING_PRESETS == {"R02": 2, "R05": 5, "R10": 10, "R20": 20}
    converted = convert_undersampling_presets({"undersamplers": ["R10", "R02", "TKL"],
                                               "undersampler": "R05"})
    assert converted["undersamplers"] == ["RND", "TKL"] and converted["undersampler"] == "RND"
    assert converted["undersampling_share"] == 66.7                    # R02: 2 / 3
    kept = convert_undersampling_presets({"undersamplers": ["R20"], "undersampling_share": 70.0})
    assert kept["undersampling_share"] == 70.0
    assert convert_undersampling_presets({"undersamplers": ["RND"]}) == {"undersamplers": ["RND"]}


def test_stored_configurations_with_presets_load(tmp_path):
    from Config import Config
    from JBGConfigurationService import _server_template
    from JBGMeta import Undersampling
    settings = _server_template()
    settings["mode"]["undersamplers"] = ["R05"]
    settings["data_source"] = dict(settings["data_source"], kind="sql")
    path = tmp_path / "configuration.json"
    path.write_text(json.dumps(settings), encoding="utf-8")
    loaded = Config.load_config_from_json(path)
    assert loaded.mode.undersamplers == ["RND"] and loaded.mode.undersampling_share == 83.3
    settings["mode"]["undersamplers"] = ["ALL"]
    path.write_text(json.dumps(settings), encoding="utf-8")
    everything = Config.load_config_from_json(path).mode.undersamplers
    assert not set(everything) & set(UNDERSAMPLING_PRESETS) and "RND" in everything
    assert Undersampling["R02"]                       # saved models refer to them


def test_the_presets_are_gone_from_the_choices():
    from JBGConfigSchema import configuration_schema
    from JBGConfigurationService import _server_template
    from JBGWebUI import translator
    fields = {f["key"]: f for f in configuration_schema("csv", translator("sv"),
                                                        _server_template())["fields"]}
    codes = [o["value"] for o in fields["mode.undersamplers"]["options"]]
    assert not set(codes) & set(UNDERSAMPLING_PRESETS) and "RND" in codes
    over, under = fields["mode.oversampling_share"], fields["mode.undersampling_share"]
    assert (over["kind"], over["role"], over["minimum"], over["maximum"]) == ("share", "over", 0.0, 50.0)
    assert (under["kind"], under["role"], under["minimum"], under["maximum"]) == ("share", "under", 50.0, 100.0)
    assert over["label"] == "Minsta klassens andel efter översampling"
    assert under["label"] == "Största klassens andel efter undersampling"


def test_the_settings_are_validated():
    from Config import Config
    Config.Mode(oversampling_share=30.0, undersampling_share=60.0).validate()
    for bad in ({"oversampling_share": 60.0}, {"oversampling_share": 0.0},
                {"undersampling_share": 40.0}, {"undersampling_share": 100.0}):
        with pytest.raises(ValueError):
            Config.Mode(**bad).validate()
    assert Config.LATER_KEYS["mode"]["oversampling_share"] is None
    assert Config.LATER_KEYS["mode"]["undersampling_share"] is None


# --- The form ----------------------------------------------------------------------------

IMBALANCED = ("row_id;f1;f2;target\n" + "".join(
    f"{i};{i % 7}.5;{i % 5}.25;{'b' if i % 5 == 0 else 'a'}\n" for i in range(1, 21))).encode()


def _form(client, project, configuration, **overrides):
    from JBGConfigSchema import configuration_schema
    from JBGConfigurationService import _server_template
    from JBGWebUI import translator
    from test_revision_292a_configuration_tab import _as_form, _form_for
    current = client.get(f"/api/projects/{project}/configurations/{configuration}").json()
    schema = configuration_schema("csv", translator("sv"), _server_template())
    shown = {"fields": [f for f in schema["fields"] if not f.get("inactive")]}
    form = _form_for(current["settings"], shown, **overrides) + \
        [("expected_version", str(current["version"]))]
    return _as_form(form)


def test_an_untouched_slider_stops_the_save_until_moved_or_standard(tmp_path):
    from test_revision_288a_project_runs import _client, _setup
    with _client(tmp_path) as client:
        project, _, configuration = _setup(client, data=IMBALANCED)     # 80 % a, 20 % b
        client.post(f"/ui/projects/{project}/open")
        url = f"/ui/configuration/{configuration}"
        stopped = client.post(url, data=_form(client, project, configuration, **{
            "f:mode.oversamplers": ["SME"], "f:mode.oversampling_share": ""}),
            follow_redirects=False)
        moved = client.post(url, data=_form(client, project, configuration, **{
            "f:mode.oversamplers": ["SME"], "f:mode.oversampling_share": "35,5"}),
            follow_redirects=False)
        after_moved = client.get(f"/api/projects/{project}/configurations/{configuration}").json()
        standard = client.post(url, data=_form(client, project, configuration, **{
            "f:mode.undersamplers": ["RND"], "f:mode.undersampling_share": "",
            "sampling_standard": "1"}), follow_redirects=False)
        after_standard = client.get(f"/api/projects/{project}/configurations/{configuration}").json()
        cleaning = client.post(url, data=_form(client, project, configuration, **{
            "f:mode.undersamplers": ["TKL"], "f:mode.undersampling_share": ""}),
            follow_redirects=False)
    assert stopped.status_code == 422
    assert "reglaget står kvar på klassens nuvarande andel" in stopped.text
    assert 'name="sampling_standard" value="1"' in stopped.text
    assert "Flytta reglaget mot 50 %, eller avmarkera samplingsmetoderna." in stopped.text
    assert moved.status_code == 303
    assert after_moved["settings"]["mode"]["oversampling_share"] == 35.5
    assert standard.status_code == 303
    assert after_standard["settings"]["mode"]["undersampling_share"] == 50.0    # two classes
    assert cleaning.status_code == 303                                         # takes no share


def test_the_slider_is_drawn_with_its_classes(tmp_path):
    from test_revision_288a_project_runs import _client, _setup
    with _client(tmp_path) as client:
        project, dataset, configuration = _setup(client, data=IMBALANCED)
        client.post(f"/ui/projects/{project}/open")
        page = client.get(f"/ui/configuration?configuration={configuration}").text
        distribution = client.get(f"/api/projects/{project}/datasets/{dataset}/"
                                  "class-distribution?column=target").json()
    assert page.count("data-share-slider") == 2
    assert 'data-role="over"' in page and 'data-role="under"' in page
    assert f"/api/projects/{project}/datasets/{dataset}/class-distribution?column=target" in page
    assert 'name="f:mode.oversampling_share" value=""' in page
    assert "Minsta klassens andel efter översampling" in page
    assert "Används av: Random" in page
    assert {c["value"]: c["count"] for c in distribution["classes"]} == {"a": 16, "b": 4}


def test_the_pipeline_picture_shows_the_share():
    from JBGConfigSchema import configuration_schema
    from JBGConfigurationService import _server_template, user_view
    from JBGWebUI import translator
    from JBGWebUIPipeline import pipeline_steps
    values = user_view(_server_template())
    values["mode"].update(oversamplers=["SME"], oversampling_share=30.0)
    steps = pipeline_steps(configuration_schema("csv", translator("sv"), _server_template()),
                           values, translate=translator("sv"), language="sv",
                           dataset_name="Data", roles=None)
    over = next(s for s in steps if s["key"] == "oversampling")
    assert over["subtitle"].endswith(" · 30,0 %")


def test_the_script_and_guides():
    script = (ROOT / "src" / "web" / "static" / "jbg.js").read_text(encoding="utf-8")
    assert 'querySelectorAll("[data-share-slider]").forEach(wireShareSlider)' in script
    assert 'var low = role === "over" ? current : 50;' in script
    sv = (ROOT / "docs" / "user_guide.sv.md").read_text(encoding="utf-8")
    en = (ROOT / "docs" / "user_guide.en.md").read_text(encoding="utf-8")
    assert "**Andelsreglagen.**" in sv and "**The share sliders.**" in en
