"""Live test for finance: reads, plus one cash booking that is removed again."""

from __future__ import annotations

from datetime import date

import pytest

from pymeinverein.api.clubs import ClubClient

from .conftest import MARKER

pytestmark = pytest.mark.live


async def test_read_finance(demo_club: ClubClient) -> None:
    club = demo_club
    accounts = await club.finance.accounts()
    assert accounts and all(a.account_name for a in accounts)
    assert await club.finance.total_balance() is not None

    with_bookings = next(a for a in accounts if a.has_bookings)
    bookings = await club.finance.bookings(with_bookings, limit=3)
    assert bookings and bookings[0].booking_amount is not None
    assert (await club.finance.booking(bookings[0].id)).id == bookings[0].id

    transactions = await club.finance.transactions()
    assert transactions
    invoices = await club.finance.transactions(type="invoice")
    assert invoices and all(t.type == "invoice" for t in invoices)
    assert (await club.finance.invoice(invoices[0].id))["number"] == invoices[0].number

    statistics = await club.dashboard.member_statistics()
    assert statistics[0].member_count > 0
    assert (await club.dashboard.finance_statistics()).data
    assert len(await club.dashboard.finance_comparison()) == 6


async def test_cash_booking_roundtrip(demo_club: ClubClient) -> None:
    club = demo_club
    cash = next((a for a in await club.finance.accounts() if a.is_cash), None)
    if cash is None:
        pytest.skip("the demo club has no cash box")
    before = cash.account_balance
    try:
        booking = await club.finance.create_cash_booking(
            cash,
            12.34,
            on=date.today(),
            contact_name=MARKER,
            purpose=f"{MARKER} booking",
        )
        assert booking.booking_amount == 12.34
        found = await club.finance.bookings(cash, search=MARKER)
        assert [b.id for b in found] == [booking.id]
        await club.finance.delete_booking(booking.id)
    finally:
        for leftover in await club.finance.bookings(cash, search=MARKER):
            await club.finance.delete_booking(leftover.id)
    assert (await club.finance.account(cash.id)).account_balance == before
