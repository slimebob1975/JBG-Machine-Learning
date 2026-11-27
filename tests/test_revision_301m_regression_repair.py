"""301m (found with the full regression at 0.20.1, 2026-11-26): the full pytest
run had 96 failures and 6 errors, none from a product fault. Tests disturbed
each other (importing GUIHandler loaded the developer's .env into the process),
and old tests outside the gate had fallen behind the code since 280-300. These
tests keep the repairs in place."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROBE = "JBG_301M_PROBE"


def test_a_test_may_leave_a_variable_behind():
    os.environ[PROBE] = "left behind"                   # as load_dotenv would


def test_the_next_test_starts_without_it():
    assert PROBE not in os.environ                      # conftest restored it


def test_the_snapshot_is_taken_before_the_project_is_imported():
    conftest = (ROOT / "tests" / "conftest.py").read_text(encoding="utf-8")
    assert conftest.index("_ENVIRONMENT = dict(os.environ)") < conftest.index("from Config import Config")
    assert "def _environment_before_the_tests():" in conftest


def test_the_old_dark_numbers_tests_are_retired_with_a_reason():
    handler = (ROOT / "tests" / "test_handler.py").read_text(encoding="utf-8")
    assert handler.count("@pytest.mark.skip(reason=RETIRED_DARK_NUMBERS)") == 5
    assert "replaced by JBG 1.3" in handler


def test_the_stand_ins_follow_the_code():
    for name in ("test_csv_model_compatibility_234.py", "test_model_compatibility_173.py",
                 "conftest.py"):
        assert "def get_categorical_limit(self): return 30" in \
            (ROOT / "tests" / name).read_text(encoding="utf-8"), name
    assert "'_keep_predictions_in_run_folder'" in \
        (ROOT / "tests" / "test_csv_real_handlers_221.py").read_text(encoding="utf-8")
    assert "monkeypatch.setattr(cv_module, 'cross_validate'" in \
        (ROOT / "tests" / "test_grid_search_timing.py").read_text(encoding="utf-8")
