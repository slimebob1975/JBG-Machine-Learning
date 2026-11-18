"""Mark a project as changed (revision 300b, asked 2026-11-18).

The Projects list is ordered by each project's last change. It changed only
when the project's own details were edited; now every change inside the
project counts: datasets (new, roles, validation, role, corrections,
deletion), configurations (new, saved, deleted), runs started and deletions.
Called inside the writing transaction, so a change that fails is not counted.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, MetaData, String, Table, update


def touch_project(connection, schema, project_id: str) -> None:
    projects = Table("jbg_projects", MetaData(schema=schema),
                     Column("project_id", String(36)),
                     Column("updated_at", DateTime(timezone=True)))
    connection.execute(update(projects).where(projects.c.project_id == project_id)
                       .values(updated_at=datetime.now(timezone.utc)))
