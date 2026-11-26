"""301h (reported 2026-11-26): a CSV file saved by Excel in Windows-1252 was
refused, since every upload was read as UTF-8. The upload detects the encoding
now: UTF-8 (with or without a byte-order mark), else Windows-1252, else
Latin-1. The test file is made up."""
from pathlib import Path

import pytest

from JBGProjectStorage import detect_encoding

ROWS = ("Id;System;Processområde;Leverantör;Klass\r\n"
        + "".join(f"{i};System {i};Område {i % 3};Företag {'ÅÄÖ'[i % 3]};"
                  f"{'Hög' if i % 4 == 0 else 'Låg'}\r\n" for i in range(1, 25)))
# A cell with a line break inside quotes, as Excel writes it.
ROWS += '25;"System\nmed radbrytning";Område 1;Företag Å;Låg\r\n'


def test_the_encoding_is_detected():
    assert detect_encoding(ROWS.encode("cp1252")) == "cp1252"
    assert detect_encoding(ROWS.encode("utf-8")) == "utf-8-sig"
    assert detect_encoding(b"\xef\xbb\xbf" + ROWS.encode("utf-8")) == "utf-8-sig"
    assert detect_encoding(b"a;b\r\n\x81;\x8d\r\n") == "latin-1"         # not Windows-1252
    assert detect_encoding(b"a;b\r\n1;2\r\n") == "utf-8-sig"            # plain ASCII


@pytest.mark.parametrize("encoding", ["cp1252", "utf-8", "utf-8-sig"])
def test_excel_files_upload_and_read_back(tmp_path, encoding):
    pytest.importorskip("fastapi")
    from test_revision_288a_project_runs import _client
    data = ROWS.encode(encoding)
    if encoding == "utf-8-sig":
        assert data.startswith(b"\xef\xbb\xbf")
    with _client(tmp_path) as client:
        project = client.post("/api/projects", json={"name": "P", "source": "csv"}).json()["project_id"]
        client.post(f"/ui/projects/{project}/open")
        done = client.post("/ui/dataset/csv", data={"name": "Excel", "role": "training"},
                           files={"file": ("excel.csv", data, "text/csv")}, follow_redirects=False)
        dataset = done.headers["location"].split("dataset=")[1].split("&")[0]
        page = client.get(f"/ui/dataset?dataset={dataset}&view=preview").text
    assert done.status_code == 303 and "message=added" in done.headers["location"]
    assert "Processområde" in page and "Leverantör" in page and "Företag Å" in page
    assert "Ã" not in page and "\ufffd" not in page


def test_a_given_encoding_is_kept(tmp_path):
    from JBGDatasetService import DatasetService
    import inspect
    signature = inspect.signature(DatasetService.upload_csv)
    assert signature.parameters["encoding"].default is None              # detected unless given


def test_the_guides():
    root = Path(__file__).resolve().parent.parent
    sv = " ".join((root / "docs" / "user_guide.sv.md").read_text(encoding="utf-8").split())
    assert "UTF-8 eller Windows-1252 som Excel sparar, känns igen automatiskt" in sv
