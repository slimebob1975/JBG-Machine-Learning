"""300c (reported 2026-11-18): copying column roles into an SQL dataset
listed every numeric column as "not numbers here". The SQL profile gives the
SQL type ("int", "decimal", ...) where the check expected "number"; SQL types
are now translated the same way as elsewhere. The message says why, with each
column's type in this dataset."""
from JBGDatasetInspection import NUMERIC_SQL_TYPES
from JBGDatasetRoles import DatasetRoles, copy_roles


def _kinds(types):
    return {name: "number" if t.lower() == "number" or t.lower() in NUMERIC_SQL_TYPES else "text"
            for name, t in types.items()}


def test_sql_numeric_types_count_as_numbers():
    source = DatasetRoles.from_mapping({"Id": "id", "Klass": "class", "Belopp": "numeric",
                                        "Ar": "numeric", "Kod": "numeric"})
    types = {"Id": "int", "Klass": "varchar", "Belopp": "decimal", "Ar": "smallint",
             "Kod": "nvarchar"}
    _, missing, not_numeric = copy_roles(source, _kinds(types))
    assert missing == [] and not_numeric == ["Kod"]              # only the text column


def test_the_page_code_translates_sql_types_and_names_them():
    from pathlib import Path
    source = (Path(__file__).resolve().parent.parent / "src" / "JBGWebUIDatasets.py").read_text(
        encoding="utf-8")
    assert "or t.lower() in NUMERIC_SQL_TYPES" in source
    assert 'not_numeric = [f"{name} ({types[name]})" for name in not_numeric]' in source
    from JBGWebUI import _load_catalog
    assert "Numeric variables in the other dataset, but stored as text in this one, so they " \
           "cannot be numeric variables here. Choose another role, for example categorical " \
           "or text:" in _load_catalog("sv")
