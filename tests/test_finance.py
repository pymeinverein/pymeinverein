"""Finance and dashboard against the mock server."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from pymeinverein import BadRequestError, LookupFailedError, MeinVereinError
from pymeinverein import NotFoundError
from pymeinverein.api.clubs import ClubClient
from pymeinverein.testing import MockServer, seed


async def test_accounts(club: ClubClient) -> None:
    accounts = await club.finance.accounts()
    assert [(a.account_name, a.account_type, a.account_balance) for a in accounts] == [
        ("Kasse", "cash", 235.6),
        ("Vereinskonto", "offlineBankAccount", 120.0),
    ]
    assert accounts[0].is_cash and not accounts[1].is_cash
    assert await club.finance.total_balance() == Decimal("355.60")
    assert (await club.finance.account("Vereinskonto")).id == seed.ACCOUNT_BANK
    with pytest.raises(LookupFailedError, match="'Kasse'"):
        await club.finance.account("Sparbuch")


async def test_bookings_newest_first(club: ClubClient) -> None:
    bookings = await club.finance.bookings("Kasse")
    assert [(b.purpose_description, b.booking_amount) for b in bookings] == [
        ("Bälle", -49.9),
        ("Getränkeverkauf", 85.5),
        ("Anfangsbestand", 200.0),
    ]
    assert bookings[0].booking_date is not None
    assert bookings[0].booking_date.date() == date(2026, 10, 20)
    assert len(await club.finance.bookings(seed.ACCOUNT_CASH, limit=2)) == 2
    found = await club.finance.bookings("Kasse", search="erika")
    assert [b.id for b in found] == [9402]


async def test_bookings_are_fetched_page_by_page(
    server: MockServer, club: ClubClient
) -> None:
    for number in range(120):
        server.state.add_booking(
            club.id, seed.ACCOUNT_CASH, "2026-11-01", "", f"Posten {number}", 1.0
        )
    server.state.requests.clear()
    bookings = await club.finance.bookings("Kasse")
    assert len(bookings) == 123
    assert len({b.id for b in bookings}) == 123
    pages = [r for r in server.state.requests if r[1].endswith("/turnover")]
    assert len(pages) == 3


async def test_the_api_needs_an_offset(club: ClubClient) -> None:
    with pytest.raises(BadRequestError) as excinfo:
        await club._transport.get(
            f"/protected/club/{club.id}/banking/account/{seed.ACCOUNT_CASH}/turnover"
        )
    assert excinfo.value.name == "BankingServiceError"


async def test_cash_booking_lifecycle(club: ClubClient) -> None:
    booking = await club.finance.create_cash_booking(
        "Kasse",
        Decimal("-12.34"),
        on=date(2026, 11, 10),
        contact_name="Bäckerei",
        purpose="Brötchen",
    )
    assert (booking.booking_amount, booking.booking_contact_name) == (
        -12.34,
        "Bäckerei",
    )
    assert booking.booking_date is not None
    assert booking.booking_date.date() == date(2026, 11, 10)
    assert (await club.finance.account("Kasse")).account_balance == 223.26

    await club.finance.delete_booking(booking.id)
    assert (await club.finance.account("Kasse")).account_balance == 235.6
    with pytest.raises(NotFoundError):
        await club.finance.booking(booking.id)


async def test_bookings_only_in_cash_boxes(club: ClubClient) -> None:
    with pytest.raises(MeinVereinError, match="not a cash box"):
        await club.finance.create_cash_booking(
            "Vereinskonto", 10, on=date(2026, 11, 10)
        )


async def test_transactions(club: ClubClient) -> None:
    everything = await club.finance.transactions()
    assert [(t.type, t.state, t.number) for t in everything] == [
        ("invoice", "Paid", "2026000001"),
        ("invoice", "Open", "2026000002"),
        ("expense", "Paid", "2026000003"),
    ]
    unpaid = await club.finance.transactions(type="invoice", state="Open")
    assert [(t.receiver, t.payment_open_amount) for t in unpaid] == [
        ("Lena Probe", 120.0)
    ]
    invoice = await club.finance.invoice(unpaid[0].id)
    assert invoice["number"] == "2026000002"
    with pytest.raises(NotFoundError):
        await club.finance.invoice(1)


async def test_dashboard(club: ClubClient) -> None:
    members = await club.dashboard.member_statistics()
    assert [
        (m.name, m.member_count, m.active_count, m.passive_count) for m in members
    ] == [
        ("Alle Abteilungen", 8, 5, 1),
        ("1. Mannschaft - Damen", 2, 2, 0),
        ("1. Mannschaft - Herren", 2, 2, 0),
    ]
    assert members[0].contact_count == 2

    finance = await club.dashboard.finance_statistics()
    assert [(e.account_name, e.balance) for e in finance.data] == [
        ("Kasse", 235.6),
        ("Vereinskonto", 120.0),
        ("Offene Forderungen", 120.0),
    ]
    assert finance.sum == 475.6

    months = await club.dashboard.finance_comparison()
    assert [(m.key, m.income_sum, m.expenses_sum) for m in months] == [
        ("2026-10", 405.5, 49.9)
    ]
