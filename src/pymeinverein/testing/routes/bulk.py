"""Bulk edits of members.

Every call answers ``{"meta": {"skips": [...], "skippedClubMemberIds": [...]},
"data": {}}``. Observed reasons for skipping: ``NO_SEPA_MANDATE`` (switching to
direct debit without a mandate) and ``NOT_A_CLUB_MEMBER`` (editing a membership
period the member does not have).
"""

from __future__ import annotations

from typing import Any

from aiohttp import web

from .._responses import bad_request, not_found
from ..state import Json
from ._base import NEW, RouteGroup, json_body
from .members import set_custom_value


class BulkRoutes(RouteGroup):
    def register(self, router: web.UrlDispatcher) -> None:
        base = f"{NEW}/members/bulk-edit"
        router.add_put(f"{base}/communication-type", self.communication_type)
        router.add_put(f"{base}/payment-types", self.payment_types)
        router.add_put(f"{base}/individual-field-data", self.individual_field_data)
        router.add_post(f"{base}/memberships", self.add_membership)
        router.add_put(f"{base}/memberships", self.edit_membership)

    async def _targets(
        self, request: web.Request
    ) -> tuple[dict[str, Any], list[Json]] | web.Response:
        club_id = self._club_id(request)
        if club_id is None:
            return not_found()
        body = await json_body(request)
        ids = body.get("clubMemberIds") if isinstance(body, dict) else None
        if not isinstance(ids, list):
            return bad_request("clubMemberIds")
        members = self.state.members[club_id]
        return body, [members[i] for i in ids if i in members]

    @staticmethod
    def _answer(skips: list[tuple[int, str]]) -> web.Response:
        return web.json_response(
            {
                "meta": {
                    "skips": [
                        {"clubMemberId": member_id, "reason": reason}
                        for member_id, reason in skips
                    ],
                    "skippedClubMemberIds": [member_id for member_id, _ in skips],
                },
                "data": {},
            }
        )

    async def communication_type(self, request: web.Request) -> web.Response:
        found = await self._targets(request)
        if isinstance(found, web.Response):
            return found
        body, members = found
        if not isinstance(body.get("communicationType"), int):
            return bad_request("communicationType")
        for member in members:
            member["communicationChannel"] = body["communicationType"]
        return self._answer([])

    async def payment_types(self, request: web.Request) -> web.Response:
        found = await self._targets(request)
        if isinstance(found, web.Response):
            return found
        body, members = found
        kind = body.get("paymentType")
        if not isinstance(kind, int):
            return bad_request("paymentType")
        skips: list[tuple[int, str]] = []
        for member in members:
            if kind == 0 and not member.get("clubMemberSepaMandates"):
                skips.append((member["id"], "NO_SEPA_MANDATE"))
            else:
                member["paymentType"]["type"] = kind
        return self._answer(skips)

    async def individual_field_data(self, request: web.Request) -> web.Response:
        found = await self._targets(request)
        if isinstance(found, web.Response):
            return found
        body, members = found
        entries = body.get("individualFieldData")
        if not isinstance(entries, list):
            return bad_request("individualFieldData")
        for member in members:
            for entry in entries:
                set_custom_value(
                    member,
                    entry["individualFieldId"],
                    entry["values"],
                    self.state.individual_fields[member["clubId"]],
                )
            if body.get("notes") is not None:
                member["notes"] = body["notes"]
        return self._answer([])

    async def add_membership(self, request: web.Request) -> web.Response:
        found = await self._targets(request)
        if isinstance(found, web.Response):
            return found
        body, members = found
        period = body.get("history")
        if not isinstance(period, dict) or not period.get("membershipStart"):
            return bad_request("history")
        for member in members:
            member.setdefault("histories", []).append(dict(period))
            self.state.sync_membership(member)
        return self._answer([])

    async def edit_membership(self, request: web.Request) -> web.Response:
        found = await self._targets(request)
        if isinstance(found, web.Response):
            return found
        body, members = found
        changes = body.get("history")
        if not isinstance(changes, dict):
            # The real service answers such bodies with a firewall page.
            return bad_request("history")
        skips: list[tuple[int, str]] = []
        for member in members:
            periods = [
                period
                for period in member.get("histories", [])
                if period.get("subAreaId") == body.get("subAreaId")
            ]
            if not periods:
                skips.append((member["id"], "NOT_A_CLUB_MEMBER"))
                continue
            for key in ("membershipEnd", "status", "isHonoured"):
                if key in changes:
                    periods[0][key] = changes[key]
            self.state.sync_membership(member)
        return self._answer(skips)
