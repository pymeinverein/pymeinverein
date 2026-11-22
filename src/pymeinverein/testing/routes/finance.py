"""Accounts, bookings, business transactions and dashboard statistics.

Observed on the real API:

* The account list has friendlier field names with ``x-api-version: v2``; the
  mock always answers in that shape.
* The booking list ("turnover") fails with ``400 BankingServiceError`` when
  the ``offset`` parameter is missing.
"""

from __future__ import annotations

from aiohttp import web

from .._responses import api_error, bad_request, data, not_found
from ..state import Json
from ._base import NEW, RouteGroup, json_body


class FinanceRoutes(RouteGroup):
    def register(self, router: web.UrlDispatcher) -> None:
        banking = f"{NEW}/banking"
        router.add_get(f"{banking}/account", self.accounts)
        router.add_get(f"{banking}/account/{{account_id}}/turnover", self.turnover)
        router.add_get(f"{banking}/booking/{{booking_id}}", self.booking)
        router.add_delete(f"{banking}/booking/{{booking_id}}", self.delete_booking)
        router.add_post(
            f"{banking}/cashjournal/{{account_id}}/booking", self.create_booking
        )
        router.add_get(f"{NEW}/businesstransactions", self.transactions)
        router.add_get(f"{NEW}/invoice/{{invoice_id}}", self.invoice)
        router.add_get(f"{NEW}/dashboard/memberStatistics", self.member_statistics)
        router.add_get(f"{NEW}/dashboard/financeStatistics", self.finance_statistics)
        router.add_get(f"{NEW}/dashboard/financeComparison", self.finance_comparison)

    def _account(self, request: web.Request) -> tuple[int, Json] | None:
        club_id = self._club_id(request)
        if club_id is None:
            return None
        for account in self.state.bank_accounts[club_id]:
            if str(account["id"]) == request.match_info["account_id"]:
                return club_id, account
        return None

    async def accounts(self, request: web.Request) -> web.Response:
        club_id = self._club_id(request)
        if club_id is None:
            return not_found()
        accounts = self.state.bank_accounts[club_id]
        total = sum(account["accountBalance"] for account in accounts)
        return data(accounts, {"totalBalance": f"{total:.2f}"})

    async def turnover(self, request: web.Request) -> web.Response:
        found = self._account(request)
        if found is None:
            return not_found()
        club_id, account = found
        if "offset" not in request.query:
            problem = ["One or more validation errors occurred. - 400"]
            return api_error(
                400,
                "BankingServiceError",
                [{"param": "BankingServiceError", "msg": problem, "value": problem}],
            )
        search = request.query.get("search", "").casefold()
        matching = sorted(
            (
                booking
                for booking in self.state.bookings[club_id].values()
                if booking["bankAccountId"] == account["id"]
                and search
                in f"{booking['bookingContactName']} {booking['purposeDescription']}".casefold()
            ),
            key=lambda booking: (booking["bookingDate"], booking["id"]),
            reverse=True,
        )
        offset = int(request.query["offset"])
        limit = int(request.query.get("limit", 20))
        return data(
            matching[offset : offset + limit],
            {"count": len(matching), "filteredCount": len(matching)},
        )

    def _booking(self, request: web.Request) -> tuple[int, Json] | None:
        club_id = self._club_id(request)
        raw = request.match_info["booking_id"]
        if club_id is None or not raw.isdecimal():
            return None
        booking = self.state.bookings[club_id].get(int(raw))
        return None if booking is None else (club_id, booking)

    async def booking(self, request: web.Request) -> web.Response:
        found = self._booking(request)
        if found is None:
            return not_found()
        return data(found[1])

    async def delete_booking(self, request: web.Request) -> web.Response:
        found = self._booking(request)
        if found is None:
            return not_found()
        club_id, booking = found
        del self.state.bookings[club_id][booking["id"]]
        self.state.sync_balances(club_id)
        return web.json_response({"meta": {}})

    async def create_booking(self, request: web.Request) -> web.Response:
        found = self._account(request)
        if found is None:
            return not_found()
        club_id, account = found
        body = await json_body(request)
        amount = body.get("bookingAmount") if isinstance(body, dict) else None
        if isinstance(amount, bool) or not isinstance(amount, (int, float)):
            return bad_request("bookingAmount")
        if account["accountType"] != "cash" or not body.get("bookingDate"):
            return bad_request("accountId")
        booking = self.state.add_booking(
            club_id,
            account["id"],
            str(body["bookingDate"]),
            body.get("bookingContactName") or "",
            body.get("purposeDescription") or "",
            float(amount),
        )
        return data({"id": booking["id"]})

    async def transactions(self, request: web.Request) -> web.Response:
        club_id = self._club_id(request)
        if club_id is None:
            return not_found()
        items = self.state.transactions[club_id]
        return data(items, {"count": len(items), "filteredCount": len(items)})

    async def invoice(self, request: web.Request) -> web.Response:
        club_id = self._club_id(request)
        if club_id is None:
            return not_found()
        for item in self.state.transactions[club_id]:
            if str(item["id"]) == request.match_info["invoice_id"]:
                return web.json_response({"data": item})
        return not_found()

    # ----------------------------------------------------------------- dashboard

    async def member_statistics(self, request: web.Request) -> web.Response:
        club_id = self._club_id(request)
        if club_id is None:
            return not_found()
        people = list(self.state.members[club_id].values())

        def row(name: str, members: list[Json]) -> Json:
            return {
                "name": name,
                "memberCount": sum(m["type"] == 1 for m in members),
                "activeCount": sum(m["type"] == 1 and m["state"] == 0 for m in members),
                "passiveCount": sum(
                    m["type"] == 1 and m["state"] == 2 for m in members
                ),
                "averageAge": None,
                "contactCount": sum(m["type"] != 1 for m in members),
            }

        rows = [row("Alle Abteilungen", people)]
        for sub in self.state.sub_areas[club_id]:
            if sub["level"] != 1:
                continue
            inside = [
                member
                for member in people
                if any(
                    area["id"] == sub["id"]
                    for period in member.get("histories", [])
                    if not period.get("isFormer")
                    for area in self._sub_area_chain(club_id, period.get("subAreaId"))
                )
            ]
            rows.append(row(sub["name"], inside))
        return web.json_response({"data": rows})

    async def finance_statistics(self, request: web.Request) -> web.Response:
        club_id = self._club_id(request)
        if club_id is None:
            return not_found()
        entries = [
            {
                "accountName": account["accountName"],
                "lastUpdate": account["accountBalanceDate"],
                "balance": account["accountBalance"],
                "type": 0,
            }
            for account in self.state.bank_accounts[club_id]
        ]
        open_amount = sum(
            item["paymentOpenAmount"] for item in self.state.transactions[club_id]
        )
        entries.append(
            {
                "accountName": "Offene Forderungen",
                "lastUpdate": None,
                "balance": open_amount,
                "type": 1,
            }
        )
        total = round(sum(entry["balance"] for entry in entries), 2)
        return web.json_response({"data": {"data": entries, "sum": total}})

    async def finance_comparison(self, request: web.Request) -> web.Response:
        club_id = self._club_id(request)
        if club_id is None:
            return not_found()
        months: dict[str, Json] = {}
        for booking in self.state.bookings[club_id].values():
            key = booking["bookingDate"][:7]
            month = months.setdefault(
                key, {"key": key, "incomeSum": 0.0, "expensesSum": 0.0}
            )
            amount = booking["bookingAmount"]
            month["incomeSum" if amount >= 0 else "expensesSum"] += abs(amount)
        return web.json_response({"data": [months[key] for key in sorted(months)]})
