"""Reports: prepared with ``POST``, downloaded by the run's process id.

Observed on the real API: required inputs (including dropdowns that have a
default value) must be sent, otherwise ``400 ... REQUIRED``; the download of an
unknown run answers ``400``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from aiohttp import web

from .. import seed
from .._responses import api_error, bad_request, not_found
from ..state import Json
from ._base import NEW, RouteGroup, json_body

_CONTENT_TYPES = {
    "pdf": "application/pdf",
    "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "csv": "text/csv",
    "xml": "application/xml",
}


class ReportRoutes(RouteGroup):
    def register(self, router: web.UrlDispatcher) -> None:
        router.add_get(f"{NEW}/reports", self.reports)
        router.add_post(f"{NEW}/reports", self.prepare)
        router.add_get(f"{NEW}/reports/{{process_id}}/download", self.download)

    async def reports(self, request: web.Request) -> web.Response:
        if self._club_id(request) is None:
            return not_found()
        return web.json_response({"meta": {}, "data": seed.REPORTS})

    async def prepare(self, request: web.Request) -> web.Response:
        club_id = self._club_id(request)
        if club_id is None:
            return not_found()
        body = await json_body(request)
        if not isinstance(body, dict):
            return bad_request("reportId")
        definition = next(
            (r for r in seed.REPORTS if r["id"] == body.get("reportId")), None
        )
        if definition is None or not body.get("reportProcessId"):
            return bad_request("reportId")
        values = body.get("values") or {}
        missing = []
        for field in definition["fields"]:
            names = (
                [f"{field['name']}Start", f"{field['name']}End"]
                if field["type"] == "date-range"
                else [field["name"]]
            )
            needed = (field.get("validators") or {}).get(
                "required"
            ) or "defaultValue" in field
            missing += [
                name for name in names if needed and values.get(name) in (None, "")
            ]
        if missing:
            return api_error(
                400,
                "BadRequestError",
                [
                    {"param": name, "msg": "REQUIRED", "value": "REQUIRED"}
                    for name in missing
                ],
            )
        rows = len(self.state.members[club_id])
        expires = (datetime.now(UTC) + timedelta(hours=2)).isoformat()
        self.state.report_runs[body["reportProcessId"]] = {
            "report": definition,
            "values": values,
        }
        return web.json_response(
            {
                "meta": {
                    "clubId": club_id,
                    "isEmptyState": False,
                    "reportId": definition["id"],
                    "reportProcessId": body["reportProcessId"],
                    "expiredAt": expires.replace("+00:00", "Z"),
                    "rowCount": rows,
                },
                "data": {
                    "report": {"meta": {"reportId": definition["id"]}, "data": []}
                },
            },
            status=201,
        )

    async def download(self, request: web.Request) -> web.Response:
        run = self.state.report_runs.get(request.match_info["process_id"])
        output = request.query.get("output-format", "")
        if run is None:
            return bad_request("reportProcessId", "NOT_FOUND", "NOT_FOUND")
        if output not in run["report"]["exportTypes"]:
            return bad_request("output-format")
        return web.Response(
            body=f"{run['report']['id']} as {output}".encode(),
            content_type=_CONTENT_TYPES[output],
        )
