"""Reports ("Auswertungen"): prepared on the server, downloaded as files."""

from __future__ import annotations

import uuid
from typing import Any

from .._transport import Transport
from ..exceptions import LookupFailedError
from ..models.reports import Report, ReportDefinition
from ._util import camel, to_payload, unwrap


class ReportsAPI:
    """Run the club's reports and download them.

    A report is prepared first (:meth:`run`) and then downloaded in one of its
    formats (:meth:`download`); :meth:`export` does both.
    """

    def __init__(self, transport: Transport, club_id: int) -> None:
        self._transport = transport
        self._base = f"/protected/club/{club_id}/reports"

    async def all(self) -> list[ReportDefinition]:
        """Return the reports with their inputs and download formats.

        ``GET /protected/club/{clubId}/reports``
        """
        payload = await self._transport.get(self._base)
        return [
            ReportDefinition.model_validate(item)
            for item in unwrap(payload, "data", f"GET {self._base}")
        ]

    async def get(self, report_id: str) -> ReportDefinition:
        """Return one report definition, e.g. ``report-income-expense``."""
        reports = await self.all()
        for report in reports:
            if report.id == report_id:
                return report
        known = ", ".join(repr(report.id) for report in reports)
        raise LookupFailedError(
            f"There is no report {report_id!r}. Known reports: {known or 'none'}"
        )

    async def run(self, report_id: str, **values: Any) -> Report:
        """Prepare a report run with the given inputs.

        Inputs use the field names of the report (see :meth:`get`), in
        ``snake_case`` or ``camelCase``. A date range is given as a pair:
        ``date=(date(2026, 1, 1), date(2026, 12, 31))``. Inputs that are left
        out get the report's default value::

            await club.reports.run(
                "report-income-expense", date=(date(2026, 1, 1), date(2026, 12, 31))
            )
            await club.reports.run("report-member-association-a", cut_off_date=date.today())

        ``POST /protected/club/{clubId}/reports``
        """
        definition = await self.get(report_id)
        given = {camel(key): value for key, value in values.items()}
        prepared: dict[str, Any] = {}
        for field in definition.fields:
            if field.name in given:
                value = given.pop(field.name)
                if field.type == "date-range":
                    start, end = value
                    prepared[f"{field.name}Start"] = to_payload(start)
                    prepared[f"{field.name}End"] = to_payload(end)
                else:
                    prepared[field.name] = to_payload(value)
            elif field.default_value is not None:
                prepared[field.name] = field.default_value
        prepared.update(to_payload(given))  # inputs the definition does not list
        prepared.update(
            {"suppressZeroAmountPrinting": False, "includeEmptyPeriods": True}
        )
        payload = await self._transport.post(
            self._base,
            {
                "reportId": report_id,
                "reportProcessId": str(uuid.uuid4()),
                "isEmptyState": False,
                "values": prepared,
            },
        )
        meta = dict(unwrap(payload, "meta", f"POST {self._base}"))
        meta["data"] = payload.get("data") or {}
        return Report.model_validate(meta)

    async def download(self, report: Report, format: str | None = None) -> bytes:
        """Download a prepared report as ``pdf``, ``excel``, ``csv`` or ``xml``.

        ``GET /protected/club/{clubId}/reports/{processId}/download?output-format=...``
        """
        if format is None:
            format = (await self.get(report.report_id)).default_export_type or "excel"
        return await self._transport.request_bytes(
            "GET",
            f"{self._base}/{report.report_process_id}/download",
            params={"output-format": format},
        )

    async def export(
        self, report_id: str, format: str | None = None, **values: Any
    ) -> bytes:
        """Run a report and download it in one step."""
        return await self.download(await self.run(report_id, **values), format)
