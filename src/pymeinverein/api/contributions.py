"""Contribution rates ("Beitragssätze") and their assignment to members.

This module defines what members owe. It does not bill anyone: creating
invoices or starting direct debits is deliberately not part of the library.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from typing import Any

from .._transport import Transport
from ..exceptions import LookupFailedError
from ..models.masterdata import ContributionRate, RateInterval, RateType
from ..models.member import BulkResult
from ._util import to_payload, unwrap

#: A contribution rate: id, exact name or model.
type RateRef = int | str | ContributionRate

#: The invoice line the web application suggests: rate name and billing period.
DEFAULT_INVOICE_TEXT = "<BEZEICHNUNG> <ABRECHNUNGSZEITRAUM>"


class ContributionsAPI:
    """Manage the contribution rates of one club."""

    def __init__(self, transport: Transport, club_id: int) -> None:
        self._transport = transport
        self._base = f"/protected/mv365/club/{club_id}/contribution"
        self._bulk = f"/protected/club/{club_id}/members/bulk-edit/contributions"

    async def rates(self) -> list[ContributionRate]:
        """Return all contribution rates.

        ``GET /protected/mv365/club/{clubId}/contribution/rates``
        """
        path = f"{self._base}/rates"
        data = unwrap(await self._transport.get(path), "data", f"GET {path}")
        return [
            ContributionRate.model_validate(rate)
            for rate in unwrap(data, "clubContributionRates", f"GET {path}")
        ]

    async def get(self, ref: RateRef) -> ContributionRate:
        """Look up a rate by id or exact name."""
        if isinstance(ref, ContributionRate):
            return ref
        rates = await self.rates()
        matches = [
            rate
            for rate in rates
            if (rate.id == ref if isinstance(ref, int) else rate.name == ref)
        ]
        if len(matches) != 1:
            names = ", ".join(repr(rate.name) for rate in rates)
            raise LookupFailedError(
                f"Expected exactly one contribution rate for {ref!r}, found "
                f"{len(matches)}. Known rates: {names or 'none'}"
            )
        return matches[0]

    async def _id(self, ref: RateRef) -> int:
        if isinstance(ref, int):
            return ref
        return (await self.get(ref)).id

    async def create(
        self,
        name: str,
        amount: Decimal | float | str,
        *,
        interval: RateInterval = RateInterval.YEARLY,
        type: RateType = RateType.REGULAR,
        vat_percent: float = 0,
        invoice_text: str = DEFAULT_INVOICE_TEXT,
        **fields: Any,
    ) -> ContributionRate:
        """Create a contribution rate.

        ``amount`` is the gross amount per ``interval``, for example
        ``create("Jugend", 60, interval=RateInterval.YEARLY)``.
        ``POST /protected/mv365/club/{clubId}/contribution/rates``
        """
        body = {
            "name": name,
            "amount": float(amount),
            "interval": int(interval),
            "type": int(type),
            "kind": 0,
            "amountType": 1,
            "vatPercent": vat_percent,
            "billingPeriod": "current",
            "isNegative": False,
            "invoiceText": invoice_text,
            "taxCategory": 0,
            "agedRates": [],
            "tags": [],
            **to_payload(fields),
        }
        path = f"{self._base}/rates"
        data = unwrap(await self._transport.post(path, body), "data", f"POST {path}")
        created = unwrap(data, "createdClubContributionRates", f"POST {path}")
        return ContributionRate.model_validate(created[0])

    async def update(self, ref: RateRef, **changes: Any) -> ContributionRate:
        """Change a rate, e.g. ``update("Jugend", amount=65)``.

        The rate is loaded, changed and sent back as a whole; the API rejects
        partial bodies.
        ``GET`` + ``PATCH /protected/mv365/club/{clubId}/contribution/rate/{id}``
        """
        path = f"{self._base}/rate/{await self._id(ref)}"
        data = unwrap(await self._transport.get(path), "data", f"GET {path}")
        current = unwrap(data, "clubContributionRate", f"GET {path}")
        body = dict(current[0] if isinstance(current, list) else current)
        body.update(to_payload(changes))
        # The API sends the amount as text but only accepts a number.
        body["amount"] = float(body["amount"])
        answer = unwrap(
            await self._transport.patch(path, body), "data", f"PATCH {path}"
        )
        return ContributionRate.model_validate(
            unwrap(answer, "createdClubContributionRate", f"PATCH {path}")
        )

    async def delete(self, ref: RateRef) -> None:
        """Delete a contribution rate.

        ``DELETE /protected/mv365/club/{clubId}/contribution/rate/{id}``
        """
        await self._transport.delete(f"{self._base}/rate/{await self._id(ref)}")

    # ---------------------------------------------------------------- assignment

    async def assign(
        self,
        member_ids: Iterable[int],
        rate: RateRef,
        *,
        next_due: date,
        last_due: date | None = None,
        overwrite: bool = False,
    ) -> BulkResult:
        """Give members a contribution rate that is first due on ``next_due``.

        ``last_due`` ends the contribution after that date. With ``overwrite``
        the members' existing contributions are replaced instead of extended.
        ``POST /protected/club/{clubId}/members/bulk-edit/contributions``
        """
        body = {
            "clubMemberIds": list(member_ids),
            "contributions": [
                {
                    "rateId": await self._id(rate),
                    "nextDueDate": to_payload(next_due),
                    "lastDueDate": to_payload(last_due),
                    "additionalContributions": [],
                }
            ],
            "overwrite": overwrite,
        }
        payload = await self._transport.post(self._bulk, body)
        return BulkResult.model_validate(unwrap(payload, "meta", f"POST {self._bulk}"))

    async def unassign(
        self, member_ids: Iterable[int], rates: Iterable[RateRef]
    ) -> BulkResult:
        """Remove contribution rates from members.

        ``DELETE /protected/club/{clubId}/members/bulk-edit/contributions``
        """
        body = {
            "clubMemberIds": list(member_ids),
            "rateIds": [await self._id(rate) for rate in rates],
        }
        payload = await self._transport.delete(self._bulk, body)
        return BulkResult.model_validate(
            unwrap(payload, "meta", f"DELETE {self._bulk}")
        )
