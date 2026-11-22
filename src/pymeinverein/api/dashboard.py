"""The figures of the web application's dashboard."""

from __future__ import annotations

from .._transport import Transport
from ..models.finance import FinanceStatistics, MemberStatistics, MonthlyFinance
from ._util import unwrap


class DashboardAPI:
    """Read-only statistics of one club."""

    def __init__(self, transport: Transport, club_id: int) -> None:
        self._transport = transport
        self._base = f"/protected/club/{club_id}/dashboard"

    async def member_statistics(self) -> list[MemberStatistics]:
        """Return member counts: first for all departments, then per department.

        ``GET /protected/club/{clubId}/dashboard/memberStatistics``
        """
        path = f"{self._base}/memberStatistics"
        payload = await self._transport.get(path)
        return [
            MemberStatistics.model_validate(item)
            for item in unwrap(payload, "data", f"GET {path}")
        ]

    async def finance_statistics(self) -> FinanceStatistics:
        """Return account balances, open receivables and upcoming payments.

        ``GET /protected/club/{clubId}/dashboard/financeStatistics``
        """
        path = f"{self._base}/financeStatistics"
        payload = await self._transport.get(path)
        return FinanceStatistics.model_validate(unwrap(payload, "data", f"GET {path}"))

    async def finance_comparison(self) -> list[MonthlyFinance]:
        """Return income and expenses of the last six months.

        ``GET /protected/club/{clubId}/dashboard/financeComparison?filter=1``
        """
        path = f"{self._base}/financeComparison"
        payload = await self._transport.get(path, params={"filter": 1})
        return [
            MonthlyFinance.model_validate(item)
            for item in unwrap(payload, "data", f"GET {path}")
        ]
