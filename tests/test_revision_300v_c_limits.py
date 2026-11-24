"""300v (asked 2026-11-24): the default limits for c are 20 for the upper bound
(beyond it the Dark Number is undefined) and 10 for the overtraining warning.
10 and 2 were too limiting in daily use. Configurations keep the values they
were saved with."""
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from Config import Config  # noqa: E402
from JBGDarkNumbers import DarkNumberCalculator as Calc  # noqa: E402
from test_revision_300r_rename import _client  # noqa: E402
from test_revision_288a_project_runs import _setup  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def test_the_defaults():
    mode = Config.Mode()
    assert (mode.dark_number_c_max, mode.dark_number_c_warning) == (20.0, 10.0)
    later = Config.LATER_KEYS["mode"]
    assert (later["dark_number_c_max"], later["dark_number_c_warning"]) == (20.0, 10.0)
    assert Calc.CORRECTION_MAX == 20.0
    from JBGDarkNumberOutOfFold import CORRECTION_MAX
    assert CORRECTION_MAX == 20.0
    mode.validate()


def test_the_bounds_follow_the_new_default():
    assert Calc.bounded_correction(19.5, "direct") == (19.5, "direct")
    assert Calc.bounded_correction(20.5, "direct")[0] == Calc.UNDEFINED
    from JBGDarkNumberOutOfFold import overtraining_factor
    assert overtraining_factor([(0.04, 0.6)] * 8)["quality"] == "reliable"         # c = 15


def test_a_lower_upper_bound_needs_a_lower_warning_level():
    with pytest.raises(ValueError):
        Config.Mode(dark_number_c_max=8.0).validate()                  # warning 10 > 8
    Config.Mode(dark_number_c_max=8.0, dark_number_c_warning=4.0).validate()


def test_saved_configurations_keep_their_values(tmp_path):
    with _client(tmp_path) as client:
        project, _, _ = _setup(client)
        base = f"/api/projects/{project}/configurations"
        kept = client.post(base, json={"name": "Sparad", "settings": {"mode": {
            "dark_number_c_max": 10.0, "dark_number_c_warning": 2.0}}}).json()
        new = client.post(base, json={"name": "Ny", "settings": {}}).json()
        kept_mode = client.get(f"{base}/{kept['configuration_id']}").json()["settings"]["mode"]
        new_mode = client.get(f"{base}/{new['configuration_id']}").json()["settings"]["mode"]
    assert (kept_mode["dark_number_c_max"], kept_mode["dark_number_c_warning"]) == (10.0, 2.0)
    assert (new_mode["dark_number_c_max"], new_mode["dark_number_c_warning"]) == (20.0, 10.0)


def test_the_texts_state_the_new_defaults():
    from JBGWebUI import _load_catalog
    catalog = _load_catalog("sv")
    texts = [k for k in catalog if "20 by default" in k]
    assert len(texts) == 2 and all("(20 som standard)" in catalog[k] for k in texts)
    assert not [k for k in catalog if "(10 by default)" in k]
    template = (ROOT / "src" / "web" / "templates" / "results.html").read_text(encoding="utf-8")
    assert "(20 by default)" in template and "(10 by default)" not in template
    sv = (ROOT / "docs" / "user_guide.sv.md").read_text(encoding="utf-8")
    en = (ROOT / "docs" / "user_guide.en.md").read_text(encoding="utf-8")
    assert "(20 som standard)" in sv and "varningsnivån (10 som standard)" in sv
    assert "varningsnivån (2" not in sv and "konfigurationen (2 som" not in sv
    assert "(10 som standard)" not in sv.replace("varningsnivån (10 som standard)", "")
    assert "för `c` (20) och varningsnivån (10)" in sv
    assert "(20 by default)" in en and "warning level (10 by default)" in en
    assert "warning level (2" not in en and "configuration (2 by default)" not in en
    assert "the upper bound for `c` (20) and the warning level (10)" in en


def test_the_log_names_the_configured_bound():
    source = (ROOT / "src" / "JBGHandler.py").read_text(encoding="utf-8")
    assert 'f"-{c_max:g}); the Dark Number is undefined (-1). "' in source
    assert 'f"-{DarkNumberCalculator.CORRECTION_MAX:g}); the Dark Number' not in source
