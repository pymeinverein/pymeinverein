"""Contribution rates and their assignment to members.

Observed on the real API: the amount is sent as text ("12.50") but must be
posted as a number - a text amount is answered with ``400 NO_NUMBER``; a
``PATCH`` needs the complete rate.
"""

from __future__ import annotations

from typing import Any

from aiohttp import web

from .._responses import api_error, data, not_found
from ..state import Json, now_iso
from ._base import NEW, RouteGroup, json_body

_BASE = "/protected/mv365/club/{club_id}/contribution"
_REQUIRED = ("name", "kind", "interval")


class ContributionRoutes(RouteGroup):
    def register(self, router: web.UrlDispatcher) -> None:
        router.add_get(f"{_BASE}/rates", self.rates)
        router.add_post(f"{_BASE}/rates", self.create)
        router.add_get(f"{_BASE}/rate/{{rate_id}}", self.get)
        router.add_patch(f"{_BASE}/rate/{{rate_id}}", self.update)
        router.add_delete(f"{_BASE}/rate/{{rate_id}}", self.delete)
        bulk = f"{NEW}/members/bulk-edit/contributions"
        router.add_post(bulk, self.assign)
        router.add_delete(bulk, self.unassign)

    def _rates(self, club_id: int) -> list[Json]:
        rates: list[Json] = self.state.master[club_id]["clubContributionRates"]
        return rates

    def _rate(self, request: web.Request) -> tuple[int, Json] | None:
        club_id = self._club_id(request)
        if club_id is None:
            return None
        for rate in self._rates(club_id):
            if str(rate["id"]) == request.match_info["rate_id"]:
                return club_id, rate
        return None

    @staticmethod
    def _errors(body: Any, *, complete: bool) -> list[Json]:
        errors: list[Json] = []
        if not isinstance(body, dict):
            body = {}
        required = _REQUIRED if complete else ("name",)
        for key in required:
            if body.get(key) is None:
                problem = ["REQUIRED", "INVALID"]
                errors.append({"param": key, "msg": problem, "value": problem})
        amount = body.get("amount", 0)
        if isinstance(amount, bool) or not isinstance(amount, (int, float)):
            errors.append({"param": "amount", "msg": ["NO_NUMBER"], "value": []})
        return errors

    async def rates(self, request: web.Request) -> web.Response:
        club_id = self._club_id(request)
        if club_id is None:
            return not_found()
        return data({"clubContributionRates": self._rates(club_id)})

    async def create(self, request: web.Request) -> web.Response:
        club_id = self._club_id(request)
        if club_id is None:
            return not_found()
        body = await json_body(request)
        errors = self._errors(body, complete=False)
        if errors:
            return api_error(400, "BadRequestError", errors)
        rate: Json = {
            "id": self.state.next_id(),
            "clubId": club_id,
            "name": body["name"],
            "activatedAt": now_iso(),
            "isNegative": bool(body.get("isNegative", False)),
            "amount": f"{float(body.get('amount', 0)):.2f}",
            "vatPercent": body.get("vatPercent", 0),
            "interval": body.get("interval", 0),
            "type": body.get("type", 0),
            "kind": body.get("kind", 0),
            "amountType": body.get("amountType", 1),
            "billingPeriod": body.get("billingPeriod", "current"),
            "invoiceText": body.get("invoiceText", ""),
            "taxCategory": body.get("taxCategory"),
            "agedRates": [],
            "tags": [],
        }
        self._rates(club_id).append(rate)
        return data({"createdClubContributionRates": [rate]})

    async def get(self, request: web.Request) -> web.Response:
        found = self._rate(request)
        if found is None:
            return not_found()
        # The real API wraps the single rate in a list.
        return data({"clubContributionRate": [found[1]]})

    async def update(self, request: web.Request) -> web.Response:
        found = self._rate(request)
        if found is None:
            return not_found()
        _, rate = found
        body = await json_body(request)
        errors = self._errors(body, complete=True)
        if errors:
            return api_error(400, "BadRequestError", errors)
        for key, value in body.items():
            if key not in ("id", "clubId", "amount"):
                rate[key] = value
        rate["amount"] = f"{float(body['amount']):.2f}"
        return data({"createdClubContributionRate": rate})

    async def delete(self, request: web.Request) -> web.Response:
        found = self._rate(request)
        if found is None:
            return not_found()
        club_id, rate = found
        self._rates(club_id).remove(rate)
        for member in self.state.members[club_id].values():
            self._drop(member, {rate["id"]})
        return data({})

    # ---------------------------------------------------------------- assignment

    @staticmethod
    def _drop(member: Json, rate_ids: set[int]) -> None:
        member["clubMemberContributionRates"] = [
            entry
            for entry in member.get("clubMemberContributionRates", [])
            if not any(
                item["clubContributionRateId"] in rate_ids
                for item in entry["clubMemberContributionRateItems"]
            )
        ]

    @staticmethod
    def _answer() -> web.Response:
        return web.json_response(
            {"meta": {"skips": [], "skippedClubMemberIds": []}, "data": {}}
        )

    async def assign(self, request: web.Request) -> web.Response:
        club_id = self._club_id(request)
        if club_id is None:
            return not_found()
        body = await json_body(request)
        rates = {rate["id"]: rate for rate in self._rates(club_id)}
        for member_id in body.get("clubMemberIds", []):
            member = self.state.members[club_id].get(member_id)
            if member is None:
                continue
            if body.get("overwrite"):
                member["clubMemberContributionRates"] = []
            for entry in body.get("contributions", []):
                rate = rates.get(entry.get("rateId"))
                if rate is None:
                    continue
                due = str(entry["nextDueDate"])[:10] + "T00:00:00.000Z"
                member.setdefault("clubMemberContributionRates", []).append(
                    {
                        "id": self.state.next_id(),
                        "clubMemberId": member_id,
                        "initialDebitDate": due,
                        "nextDueDate": due,
                        "endDate": entry.get("lastDueDate"),
                        "clubMemberContributionRateItems": [
                            {
                                "id": self.state.next_id(),
                                "clubContributionRateId": rate["id"],
                                "amount": rate["amount"],
                                "itemCount": "1.00",
                                "billed": False,
                            }
                        ],
                    }
                )
        return self._answer()

    async def unassign(self, request: web.Request) -> web.Response:
        club_id = self._club_id(request)
        if club_id is None:
            return not_found()
        body = await json_body(request)
        rate_ids = set(body.get("rateIds", []))
        for member_id in body.get("clubMemberIds", []):
            member = self.state.members[club_id].get(member_id)
            if member is not None:
                self._drop(member, rate_ids)
        return self._answer()
