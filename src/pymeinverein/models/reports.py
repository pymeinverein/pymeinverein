"""Models for reports ("Auswertungen")."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .base import ApiModel


class ReportField(ApiModel):
    """An input of a report, e.g. a date range or a dropdown."""

    name: str
    #: ``date``, ``date-range``, ``dropdown``, ``checkbox-multi-select``, ...
    type: str | None = None
    validators: dict[str, Any] | None = None
    options: list[Any] | None = None
    default_value: Any = None

    @property
    def required(self) -> bool:
        return bool((self.validators or {}).get("required"))


class ReportDefinition(ApiModel):
    """A report the club can run."""

    id: str
    #: 1 = finance, 2 = member association report (as observed).
    categories: list[int] = []
    fields: list[ReportField] = []
    #: Formats it can be downloaded in: ``pdf``, ``excel``, ``csv``, ``xml``.
    export_types: list[str] = []
    default_export_type: str | None = None


class Report(ApiModel):
    """A prepared report run. Download it with ``club.reports.download``."""

    report_id: str
    #: Id of this run; the download refers to it.
    report_process_id: str
    row_count: int | None = None
    #: Until when the run can be downloaded.
    expired_at: datetime | None = None
    #: The report's content as the API sends it (table configuration and rows).
    data: dict[str, Any] = {}
