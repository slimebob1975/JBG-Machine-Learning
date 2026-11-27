"""Owner-bound dataset service for the HTTP API (revision 286b).

Datasets belong to a project and inherit its source type (enforced by the 285k
repository). SQL datasets name a catalog and table; CSV datasets are uploaded
into the project's own storage (JBGProjectStorage) and referenced by an opaque
artifact ID. Nothing here reads SQL data or deletes datasets; validation (the
"Validate dataset" button) and deletion follow in later revisions, so new
datasets stay "unverified".
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any, BinaryIO

from JBGApplicationContracts import DataSourceKind
from JBGDatasets import Dataset, DatasetRepository, DatasetRole, DuplicateDatasetName
from JBGProjectService import ProjectService
from Storage.CSVDatasetCatalog import csv_file_name_for
from JBGProjectStorage import (DEFAULT_CSV_ROOT, MAX_UPLOAD_BYTES, detect_delimiter,
                               detect_encoding,
                               project_csv_storage, register_csv_upload)


class DatasetUnavailable(LookupError):
    """Unknown dataset, or a dataset of another user's project."""


class DatasetConflict(ValueError):
    """The project already has a dataset with that name."""


class UploadTooLarge(ValueError):
    """The uploaded file exceeds the 25 MB limit."""


class WrongSourceType(ValueError):
    """SQL data for a CSV project, or the other way round."""


def dataset_response(dataset: Dataset, *, upload=None) -> dict[str, Any]:
    response = {"dataset_id": dataset.dataset_id, "project_id": dataset.project_id,
                "name": dataset.name, "source": dataset.source.value,
                "role": dataset.role.value, "active_training": dataset.active_training,
                "validation_state": dataset.validation_state.value,
                "created_at": dataset.created_at.isoformat(),
                "updated_at": dataset.updated_at.isoformat()}
    if dataset.source is DataSourceKind.SQL:
        response.update(catalog=dataset.catalog, table=dataset.table)
    if upload is not None:
        # Structure of the stored file, for the GUI's preview step.
        response["upload"] = {"rows": upload.rows, "columns": list(upload.columns),
                              "delimiter": upload.delimiter, "encoding": upload.encoding,
                              "id_candidates": list(upload.id_candidates)}       # 301i
    return response


def _role(value: str) -> DatasetRole:
    try:
        return DatasetRole(value)
    except ValueError:
        raise ValueError("role must be training, prediction or mixed") from None


class DatasetService:
    def __init__(self, repository: DatasetRepository, projects: ProjectService, *,
                 csv_root: Path = DEFAULT_CSV_ROOT, compatibility=None) -> None:
        if not isinstance(repository, DatasetRepository):
            raise TypeError("DatasetRepository required")
        if not isinstance(projects, ProjectService):
            raise TypeError("ProjectService required")
        self._repository = repository
        self._projects = projects
        self._csv_root = Path(csv_root)
        self.sweep_excel()                     # 301n: everyone's old workbooks, at start
        # 293a: check(principal, project_id, candidate) for prediction datasets.
        self._compatibility = compatibility

    def _project(self, owner: str, project_id: str, source: DataSourceKind | None = None):
        project = self._projects.require(owner, project_id)
        if source is not None and project.source is not source:
            raise WrongSourceType(f"this is a {project.source.value.upper()} project")
        return project

    def list(self, owner: str, project_id: str) -> list[dict[str, Any]]:
        self._project(owner, project_id)
        return [dataset_response(d) for d in self._repository.list_for_project(owner, project_id)]

    def get(self, owner: str, project_id: str, dataset_id: str) -> dict[str, Any]:
        self._project(owner, project_id)
        try:
            return dataset_response(self._repository.get_owned(owner, project_id, dataset_id))
        except KeyError:
            raise DatasetUnavailable("dataset unavailable") from None

    def _check_prediction(self, principal, project_id, role, candidate) -> None:
        """293a: a prediction dataset must fit the active training dataset."""
        if role is DatasetRole.PREDICTION and self._compatibility is not None \
                and principal is not None:
            self._compatibility(principal, project_id, candidate)

    def create_sql(self, owner: str, project_id: str, *, name: str, role: str,
                   catalog: str, table: str, principal=None) -> dict[str, Any]:
        from types import SimpleNamespace
        self._project(owner, project_id, DataSourceKind.SQL)
        role_value = _role(role)
        if role_value is DatasetRole.PREDICTION:
            # Names are checked by the repository before anything is read.
            from JBGDatasets import _plain_sql_names
            _plain_sql_names(catalog, table)
        self._check_prediction(principal, project_id, role_value, SimpleNamespace(
            source=DataSourceKind.SQL, catalog=catalog, table=table, registration_id=None))
        try:
            dataset = self._repository.create(owner, project_id, name, _role(role),
                                              catalog=catalog, table=table)
        except DuplicateDatasetName:
            raise DatasetConflict("dataset name already exists") from None
        return dataset_response(dataset)

    def upload_csv(self, owner: str, project_id: str, *, name: str, role: str,
                   stream: BinaryIO, filename: str | None = None,
                   delimiter: str | None = None,
                   encoding: str | None = None, principal=None) -> dict[str, Any]:
        """Store an uploaded CSV in the project's storage and register it."""
        project = self._project(owner, project_id, DataSourceKind.CSV)
        role = _role(role)
        repository, scope = project_csv_storage(project.project_id, root=self._csv_root)
        with tempfile.TemporaryDirectory(prefix="jbg_upload_") as folder:
            path = Path(folder) / "upload.csv"
            with path.open("wb") as target:
                # Copy at most limit + 1 bytes, so a huge upload is never read whole.
                copied = _copy_limited(stream, target, MAX_UPLOAD_BYTES + 1)
            if copied > MAX_UPLOAD_BYTES:
                raise UploadTooLarge("CSV file exceeds 25 MB")
            if encoding is None:                    # 301h: detected, not assumed UTF-8
                encoding = detect_encoding(path.read_bytes())
            if delimiter is None:
                with path.open("rb") as reader:
                    delimiter = detect_delimiter(reader.read(64 * 1024), encoding)
            id_added = False
            if role is DatasetRole.PREDICTION and \
                    self._training_id_column(owner, project_id) == self.ID_COLUMN:
                # 301n: a model trained with JBG_RadId (301i) needs the column in the
                # file to predict; a prediction file without it gets it, numbered 1,
                # 2, 3 ... the same way.
                raw = path.read_bytes()
                if self.ID_COLUMN not in _csv_header(raw, delimiter, encoding):
                    path.write_bytes(_with_id_column(raw, self.ID_COLUMN, delimiter, encoding))
                    id_added = True
            upload = register_csv_upload(repository, scope, path, delimiter=delimiter,
                                         encoding=encoding, original_name=filename)
        try:
            from types import SimpleNamespace
            self._check_prediction(principal, project_id, role, SimpleNamespace(
                source=DataSourceKind.CSV, catalog=None, table=None,
                registration_id=upload.artifact_id))
            dataset = self._repository.create(owner, project_id, name, role,
                                              registration_id=upload.artifact_id)
        except BaseException as error:
            # Do not leave an unreferenced file behind (e.g. duplicate name).
            from Storage.CSVDatasetCatalog import erase_csv_dataset
            try:
                erase_csv_dataset(repository, scope, upload.artifact_id)
            except Exception:
                pass
            if isinstance(error, DuplicateDatasetName):
                raise DatasetConflict("dataset name already exists") from None
            raise
        response = dataset_response(dataset, upload=upload)
        response["upload"]["id_added"] = id_added                              # 301n
        return response

    def _training_id_column(self, owner: str, project_id: str) -> str | None:
        """301n: the ID column of the project's active training dataset."""
        try:
            active = next((d for d in self._repository.list_for_project(owner, project_id,
                                                                        limit=500)
                           if d.active_training), None)
            roles = self._repository.get_roles(owner, project_id, active.dataset_id) \
                if active is not None else None
            return roles.id_column if roles is not None else None
        except Exception:
            return None

    # --- 301k: Excel workbooks, one CSV dataset per chosen sheet -------------------

    EXCEL_ROOT = Path(tempfile.gettempdir()) / "jbg_excel"
    EXCEL_KEEP_SECONDS = 24 * 3600

    def sweep_excel(self, now: float | None = None) -> int:
        """301n: remove every user's kept workbooks older than a day (read_excel
        only cleared the uploading user's own). Returns how many files went."""
        import time
        now = time.time() if now is None else now
        removed = 0
        try:
            folders = [f for f in self.EXCEL_ROOT.iterdir() if f.is_dir()]
        except OSError:
            return 0
        for folder in folders:
            for old in folder.iterdir():
                try:
                    if now - old.stat().st_mtime > self.EXCEL_KEEP_SECONDS:
                        old.unlink()
                        removed += 1
                except OSError:
                    pass
            try:
                folder.rmdir()                  # only when empty
            except OSError:
                pass
        return removed

    def _excel_folder(self, owner: str) -> Path:
        import hashlib
        return self.EXCEL_ROOT / hashlib.sha256(owner.encode("utf-8")).hexdigest()[:24]

    def _excel_paths(self, owner: str, token: str) -> tuple[Path, Path]:
        import re
        if not re.fullmatch(r"[0-9a-f]{32}", token or ""):
            raise ExcelUnavailable("workbook unavailable")
        folder = self._excel_folder(owner)
        return folder / f"{token}.xlsx", folder / f"{token}.json"

    def read_excel(self, owner: str, project_id: str, *, stream: BinaryIO,
                   filename: str | None) -> dict[str, Any]:
        """301k (asked 2026-11-26): keep an uploaded workbook for its owner for a
        day and list its sheets. ``add_excel_sheets`` then adds the chosen ones."""
        import json
        import time
        from uuid import uuid4
        from JBGExcelImport import sheet_overview
        self._project(owner, project_id, DataSourceKind.CSV)
        folder = self._excel_folder(owner)
        folder.mkdir(parents=True, exist_ok=True)
        for old in folder.iterdir():                      # workbooks left from before
            try:
                if time.time() - old.stat().st_mtime > self.EXCEL_KEEP_SECONDS:
                    old.unlink()
            except OSError:
                pass
        token = uuid4().hex
        book, meta = self._excel_paths(owner, token)
        with book.open("wb") as target:
            copied = _copy_limited(stream, target, MAX_UPLOAD_BYTES + 1)
        if copied > MAX_UPLOAD_BYTES:
            book.unlink(missing_ok=True)
            raise UploadTooLarge("Excel file exceeds 25 MB")
        try:
            sheets = sheet_overview(book)
        except ValueError:
            book.unlink(missing_ok=True)
            raise
        state = {"project_id": project_id, "filename": Path(filename or "arbetsbok.xlsx").name,
                 "sheets": sheets, "results": []}
        meta.write_text(json.dumps(state), encoding="utf-8")
        return dict(state, token=token)

    def excel_state(self, owner: str, project_id: str, token: str) -> dict[str, Any]:
        import json
        book, meta = self._excel_paths(owner, token)
        try:
            state = json.loads(meta.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise ExcelUnavailable("workbook unavailable") from None
        if state.get("project_id") != project_id:
            raise ExcelUnavailable("workbook unavailable")
        return dict(state, token=token, available=book.exists())

    def add_excel_sheets(self, owner: str, project_id: str, token: str, choices: list,
                         principal=None) -> list:
        """301k: each chosen sheet ({"sheet", "name", "role"}) as a CSV dataset,
        through the ordinary CSV upload. One result per sheet: the dataset, or
        why it was not added."""
        import json
        from JBGDatasetRoles import IncompatibleDataset
        from JBGExcelImport import ExcelRefused, sheet_to_csv
        state = self.excel_state(owner, project_id, token)
        book, meta = self._excel_paths(owner, token)
        if not book.exists():
            raise ExcelUnavailable("workbook unavailable")
        known = {s["sheet"] for s in state["sheets"]}
        results = []
        for choice in choices:
            sheet, name, role = choice.get("sheet"), choice.get("name"), choice.get("role")
            entry = {"sheet": sheet, "name": name, "role": role}
            if sheet not in known:
                results.append(dict(entry, error="no_sheet"))
                continue
            try:
                with tempfile.TemporaryDirectory(prefix="jbg_sheet_") as folder:
                    csv_path = Path(folder) / "sheet.csv"
                    sheet_to_csv(book, sheet, csv_path)
                    with csv_path.open("rb") as stream:
                        created = self.upload_csv(owner, project_id, name=name, role=role,
                                                  stream=stream, filename=csv_file_name_for(name),
                                                  delimiter=";", encoding="utf-8-sig",
                                                  principal=principal)
                results.append(dict(entry, dataset_id=created["dataset_id"],
                                    rows=created["upload"]["rows"],
                                    id_candidates=created["upload"]["id_candidates"],
                                    id_added=created["upload"].get("id_added", False)))
            except ExcelRefused as refused:
                results.append(dict(entry, error=str(refused)))
            except DatasetConflict:
                results.append(dict(entry, error="duplicate"))
            except UploadTooLarge:
                results.append(dict(entry, error="too_large"))
            except IncompatibleDataset:
                results.append(dict(entry, error="incompatible"))
            except (ValueError, TypeError):
                results.append(dict(entry, error="bad_sheet"))
        state.pop("token", None)
        state.pop("available", None)
        state["results"] = results
        meta.write_text(json.dumps(state), encoding="utf-8")
        return results

    ID_COLUMN = "JBG_RadId"                    # 301i (decided 2026-11-26)

    def add_id_column(self, owner: str, project_id: str, dataset_id: str) -> dict[str, Any]:
        """301i (asked 2026-11-26): a CSV dataset where no column can be the ID
        (filled in and unique on every row) gets one: JBG_RadId, numbered 1, 2,
        3 ... first in the file, written as a new version of the file (decided
        2026-11-26), as corrections are. Earlier versions stay, as runs and
        models refer to them. Refused for SQL datasets (JBG never changes
        tables), when a column can already be the ID, or when JBG_RadId exists."""
        import csv
        import io
        from CSVColumnSchema import inspect_csv_columns
        from JBGProjectStorage import csv_upload_format
        project = self._project(owner, project_id, DataSourceKind.CSV)
        try:
            dataset = self._repository.get_owned(owner, project_id, dataset_id)
        except KeyError:
            raise DatasetUnavailable("dataset unavailable") from None
        if dataset.source is not DataSourceKind.CSV:
            raise IdColumnRefused("not_csv")
        repository, scope = project_csv_storage(project.project_id, root=self._csv_root)
        form = csv_upload_format(repository, scope, dataset.registration_id)
        with tempfile.TemporaryDirectory(prefix="jbg_id_") as folder:
            source = Path(folder) / "current.csv"
            with repository.open_artifact(scope, dataset.registration_id) as stream, \
                    source.open("wb") as target:
                shutil.copyfileobj(stream, target)
            schema = inspect_csv_columns(source, delimiter=form["delimiter"],
                                         encoding=form["encoding"])
            if self.ID_COLUMN in schema.columns:
                raise IdColumnRefused("exists")
            if schema.unique_id_candidates:
                raise IdColumnRefused("has_id_candidate")
            target = Path(folder) / "with_id.csv"
            target.write_bytes(_with_id_column(source.read_bytes(), self.ID_COLUMN,
                                               form["delimiter"], form["encoding"],
                                               form["quotechar"]))
            upload = register_csv_upload(repository, scope, target, delimiter=form["delimiter"],
                                         encoding=form["encoding"],
                                         original_name=csv_file_name_for(dataset.name))
        updated = self._repository.replace_csv_file(owner, project_id, dataset_id,
                                                    upload.artifact_id)
        return dataset_response(updated, upload=upload)

    def csv_file(self, owner: str, project_id: str, dataset_id: str) -> tuple[bytes, str]:
        """299b: a CSV dataset's current file (with any corrected classes) and a
        file name, for its owner."""
        project = self._project(owner, project_id, DataSourceKind.CSV)
        try:
            dataset = self._repository.get_owned(owner, project_id, dataset_id)
        except KeyError:
            raise DatasetUnavailable("dataset unavailable") from None
        repository, scope = project_csv_storage(project.project_id, root=self._csv_root)
        try:
            with repository.open_artifact(scope, dataset.registration_id) as stream:
                return stream.read(), f"{dataset.name}.csv"
        except (OSError, ValueError):
            raise DatasetUnavailable("dataset file unavailable") from None

    def activate(self, owner: str, project_id: str, dataset_id: str) -> dict[str, Any]:
        self._project(owner, project_id)
        try:
            return dataset_response(self._repository.activate_training(owner, project_id,
                                                                        dataset_id))
        except KeyError:
            raise DatasetUnavailable("dataset unavailable") from None


    def change_role(self, owner: str, project_id: str, dataset_id: str,
                    role: str) -> dict[str, Any]:
        """298f: switch a dataset between training and mixed (fixed refusal
        for prediction datasets and the prediction role)."""
        self._project(owner, project_id)
        try:
            return dataset_response(self._repository.change_role(
                owner, project_id, dataset_id, _role(role)))
        except KeyError:
            raise DatasetUnavailable("dataset unavailable") from None

    def rename(self, owner: str, project_id: str, dataset_id: str, *,
               name: str) -> dict[str, Any]:
        """300r: a new display name; run lists show it at once."""
        self._project(owner, project_id)
        try:
            return dataset_response(self._repository.rename(owner, project_id, dataset_id,
                                                            name))
        except DuplicateDatasetName:
            raise DatasetConflict("dataset name already exists") from None
        except KeyError:
            raise DatasetUnavailable("dataset unavailable") from None


class ExcelUnavailable(LookupError):
    """301k: the uploaded workbook is gone (older than a day) or not this owner's."""


class IdColumnRefused(ValueError):
    """301i: an ID column cannot be added (the reason is a code)."""


def _csv_header(raw: bytes, delimiter: str, encoding: str) -> list:
    import csv
    import io
    text = raw.decode(encoding, errors="replace")
    return next(csv.reader(io.StringIO(text, newline=""), delimiter=delimiter), [])


def _with_id_column(raw: bytes, name: str, delimiter: str, encoding: str,
                    quotechar: str = '"') -> bytes:
    """301i, 301n: the file with an ID column first, numbered 1, 2, 3 ...
    Blank lines are not rows. Written in the file's own encoding and delimiter."""
    import csv
    import io
    rows = list(csv.reader(io.StringIO(raw.decode(encoding), newline=""), delimiter=delimiter,
                           quotechar=quotechar))
    numbered = [[name] + rows[0]] if rows else [[name]]
    number = 0
    for row in rows[1:]:
        if not any(cell.strip() for cell in row):
            continue
        number += 1
        numbered.append([str(number)] + row)
    out = io.StringIO(newline="")
    csv.writer(out, delimiter=delimiter, quotechar=quotechar,
               lineterminator="\r\n").writerows(numbered)
    return out.getvalue().encode(encoding)


def _copy_limited(source: BinaryIO, target: BinaryIO, limit: int) -> int:
    copied = 0
    while copied < limit:
        chunk = source.read(min(1024 * 1024, limit - copied))
        if not chunk:
            break
        target.write(chunk)
        copied += len(chunk)
    return copied
