"""Finances: accounts, bookings, business transactions.

Deliberately limited. The library reads the club's finances and can add or
remove bookings in a *cash box*. It does not create invoices, and it never
starts SEPA direct debits, bank transfers or online banking - those move real
money or create legally relevant documents.
"""

from __future__ import annotations

import builtins
from datetime import date
from decimal import Decimal
from typing import Any

from .._transport import Transport
from ..exceptions import LookupFailedError, MeinVereinError
from ..models.finance import BankAccount, Booking, BusinessTransaction
from ._util import to_payload, unwrap

#: An account: id, exact name or model.
type AccountRef = int | str | BankAccount

_PAGE = 50


class FinanceAPI:
    """Read the finances of one club and keep a cash box."""

    def __init__(self, transport: Transport, club_id: int) -> None:
        self._transport = transport
        self._base = f"/protected/club/{club_id}"
        self._banking = f"/protected/club/{club_id}/banking"

    # ------------------------------------------------------------------ accounts

    async def accounts(self) -> builtins.list[BankAccount]:
        """Return the club's cash boxes and bank accounts.

        ``GET /protected/club/{clubId}/banking/account`` with
        ``x-api-version: v2`` (without it the fields have different names).
        """
        path = f"{self._banking}/account"
        payload = await self._transport.get(path, api_version="v2")
        return [
            BankAccount.model_validate(item)
            for item in unwrap(payload, "data", f"GET {path}")
        ]

    async def account(self, ref: AccountRef) -> BankAccount:
        """Look up an account by id or exact name."""
        if isinstance(ref, BankAccount):
            return ref
        accounts = await self.accounts()
        matches = [
            item
            for item in accounts
            if (item.id == ref if isinstance(ref, int) else item.account_name == ref)
        ]
        if len(matches) != 1:
            names = ", ".join(repr(item.account_name) for item in accounts)
            raise LookupFailedError(
                f"Expected exactly one account for {ref!r}, found {len(matches)}. "
                f"Known accounts: {names or 'none'}"
            )
        return matches[0]

    async def _account_id(self, ref: AccountRef) -> int:
        if isinstance(ref, int):
            return ref
        return (await self.account(ref)).id

    async def total_balance(self) -> Decimal:
        """Return the sum of all account balances.

        ``GET /protected/club/{clubId}/banking/account`` (field ``meta.totalBalance``)
        """
        path = f"{self._banking}/account"
        payload = await self._transport.get(path, api_version="v2")
        meta = unwrap(payload, "meta", f"GET {path}")
        return Decimal(str(unwrap(meta, "totalBalance", f"GET {path}")))

    # ------------------------------------------------------------------ bookings

    async def bookings(
        self,
        account: AccountRef,
        *,
        search: str | None = None,
        limit: int | None = None,
    ) -> builtins.list[Booking]:
        """Return the bookings of an account, newest first.

        ``search`` filters by text; ``limit`` caps the number of bookings
        (default: all, fetched page by page).
        ``GET /protected/club/{clubId}/banking/account/{accountId}/turnover``
        with ``offset`` and ``limit`` (the API fails without ``offset``).
        """
        path = f"{self._banking}/account/{await self._account_id(account)}/turnover"
        found: builtins.list[Booking] = []
        while limit is None or len(found) < limit:
            size = _PAGE if limit is None else min(_PAGE, limit - len(found))
            params: dict[str, str | int] = {"offset": len(found), "limit": size}
            if search:
                params["search"] = search
            payload = await self._transport.get(path, params=params, api_version="v2")
            page = unwrap(payload, "data", f"GET {path}")
            found.extend(Booking.model_validate(item) for item in page)
            total = int((payload.get("meta") or {}).get("filteredCount", 0))
            if not page or len(found) >= total:
                break
        return found

    async def booking(self, booking_id: int) -> Booking:
        """Return one booking.

        ``GET /protected/club/{clubId}/banking/booking/{bookingId}``
        """
        path = f"{self._banking}/booking/{booking_id}"
        payload = await self._transport.get(path)
        return Booking.model_validate(unwrap(payload, "data", f"GET {path}"))

    async def create_cash_booking(
        self,
        account: AccountRef,
        amount: Decimal | float,
        *,
        on: date,
        contact_name: str = "",
        purpose: str = "",
    ) -> Booking:
        """Enter a booking in a cash box.

        ``amount`` is positive for money received and negative for money spent.
        Only accounts of type ``cash`` are accepted; bank accounts get their
        bookings from the bank.
        ``POST /protected/club/{clubId}/banking/cashjournal/{accountId}/booking``
        """
        target = await self.account(account)
        if not target.is_cash:
            raise MeinVereinError(
                f"Account {target.account_name!r} is not a cash box "
                f"(type {target.account_type!r}); bookings can only be entered "
                "by hand in cash boxes"
            )
        path = f"{self._banking}/cashjournal/{target.id}/booking"
        payload = await self._transport.post(
            path,
            {
                "accountId": target.id,
                "bookingAmount": float(amount),
                "bookingContactName": contact_name,
                "bookingDate": to_payload(on),
                "purposeDescription": purpose,
            },
        )
        created = unwrap(payload, "data", f"POST {path}")
        return await self.booking(int(unwrap(created, "id", f"POST {path}")))

    async def delete_booking(self, booking_id: int) -> None:
        """Delete a booking that was entered by hand.

        ``DELETE /protected/club/{clubId}/banking/booking/{bookingId}``
        """
        await self._transport.delete(f"{self._banking}/booking/{booking_id}")

    # ------------------------------------------------------ invoices and so on

    async def transactions(
        self, *, type: str | None = None, state: str | None = None
    ) -> builtins.list[BusinessTransaction]:
        """Return invoices, expenses, donations, credit notes and cancellations.

        ``type`` and ``state`` filter in Python, e.g. ``type="invoice"``,
        ``state="Open"``.
        ``GET /protected/club/{clubId}/businesstransactions``
        """
        path = f"{self._base}/businesstransactions"
        payload = await self._transport.get(path)
        items = [
            BusinessTransaction.model_validate(item)
            for item in unwrap(payload, "data", f"GET {path}")
        ]
        return [
            item
            for item in items
            if (type is None or item.type == type)
            and (state is None or item.state == state)
        ]

    async def invoice(self, invoice_id: int) -> dict[str, Any]:
        """Return the full data of one invoice as the API sends it.

        ``GET /protected/club/{clubId}/invoice/{invoiceId}``
        """
        path = f"{self._base}/invoice/{invoice_id}"
        payload = await self._transport.get(path)
        data: dict[str, Any] = unwrap(payload, "data", f"GET {path}")
        return data
