"""300n (asked 2026-11-20): JBG 1.3's adjustable parts as configuration
settings (the flip test's repeats, the upper bound for c, the warning level
for overtraining), stored with each result; an overtraining warning based on
c; and the calculation table in words (capped, the correction's basis, empty
values), which still showed "False", "direct" and "N/A"."""
import json
import warnings

import pandas as pd
import pytest

from JBGDarkNumbers import DarkNumberCalculator as Calc


def test_the_settings_and_their_defaults():
    from Config import Config
    from JBGConfigSchema import configuration_schema
    from JBGConfigurationService import _server_template
    from JBGWebUI import translator
    later = Config.LATER_KEYS["mode"]
    assert (later["dark_number_c_max"], later["dark_number_c_warning"],
            later["dark_number_flip_repeats"]) == (20.0, 10.0, 2)       # 300v: were 10 and 2
    for bad in ({"dark_number_c_max": 1.0}, {"dark_number_c_warning": 25.0},
                {"dark_number_flip_repeats": 0}):
        with pytest.raises(ValueError):
            Config.Mode(**bad).validate()
    labels = {f["key"]: f["label"] for f in configuration_schema(
        "csv", translator("sv"), _server_template())["fields"]}
    assert labels["mode.dark_number_flip_repeats"] == "Upprepningar i korrektionstestet"
    assert labels["mode.dark_number_c_max"] == "Övre gräns för c"
    assert labels["mode.dark_number_c_warning"] == "Varna för överträning när c är över"


def test_the_upper_bound_is_a_parameter():
    # 300v: the default upper bound is 20, so c = 25 is out of bounds by default.
    assert Calc.bounded_correction(25.0, "direct")[0] == -1.0
    assert Calc.bounded_correction(25.0, "direct", c_max=30.0) == (25.0, "direct")
    from JBGDarkNumberOutOfFold import overtraining_factor
    pairs = [(0.024, 0.6)] * 8                                          # c = 25
    assert overtraining_factor(pairs)["quality"] == "not_estimable"
    assert overtraining_factor(pairs, c_max=30.0)["quality"] == "reliable"


def _run(**mode):
    import test_dark_number_dense_input as dense
    from types import SimpleNamespace
    X, y = dense.dataset()
    models = dense.fitted_models(X, y)
    handler = dense.handler()
    handler.handler.config.mode = SimpleNamespace(dark_number_sampling_policy="PIPELINE", **mode)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        dense.run(handler, X, y, models)
    return handler


def test_the_repeats_and_the_warning_level_are_used(monkeypatch):
    import JBGDarkNumberCorrectionFactor as factor
    seen = []
    original = factor.DarkNumberCorrectionFactorEstimator.__init__

    def recording(self, *args, **kwargs):
        seen.append(kwargs.get("n_repeats"))
        original(self, *args, **kwargs)
    monkeypatch.setattr(factor.DarkNumberCorrectionFactorEstimator, "__init__", recording)
    handler = _run(dark_number_flip_repeats=3, dark_number_c_max=10.0, dark_number_c_warning=1.0)
    assert seen and set(seen) == {3}
    frame = handler.dark_numbers
    assert "corr_overtrained" in frame.columns
    defined = frame[(frame["corr"] != Calc.UNDEFINED) & (frame["corr"] > 1.0)]
    assert defined["corr_overtrained"].all()                         # warning level 1
    logged = [m for m in handler.handler.logger.warnings if "learns some of the deliberately" in m]
    assert logged or defined.empty


def test_the_record_stores_the_values_used():
    from types import SimpleNamespace
    from JBGDarkNumberRecord import parameters
    config = SimpleNamespace(
        mode=SimpleNamespace(dark_number_method=SimpleNamespace(name="LINEAR"),
                             dark_number_alpha=SimpleNamespace(name="SEPARATED"),
                             dark_number_flip_fraction=0.2, dark_number_c_max=15.0,
                             dark_number_c_warning=3.0, dark_number_flip_repeats=4),
        get_dark_number_calculation_type=lambda: "separated_alpha",
        get_dark_number_target=lambda: "")
    used = parameters(config, {})
    assert (used["correction_max"], used["c_warning"], used["flip_test_repeats"]) == (15.0, 3.0, 4)


def test_the_table_in_words():
    from JBGWebUI import translator
    from JBGWebUIResults import readable_dark_table
    detail = {"columns": ["Model type", "capped", "corr_source", "corr_in_sample",
                          "corr_overtrained"],
              "rows": [["D_cv_test - M", "False", "not applied (test part)", "N/A", "False"],
                       ["D_cv_full - M", "True", "direct", "6.261", "True"],
                       ["D_re_full - M", "False", "undefined/out_of_bounds (direct)", "nan", ""]]}
    readable_dark_table(detail, translator("sv"), "sv")
    assert detail["rows"][0][1:] == ["Nej", "används inte (testdel)", "–", "Nej"]
    assert detail["rows"][1][1:3] == ["Ja", "direkt (ommärkningstestet)"]
    assert detail["rows"][1][4] == "Ja"
    assert detail["rows"][2][2:4] == ["odefinierad: c ligger utanför gränserna", "–"]
