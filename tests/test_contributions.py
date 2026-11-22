"""Contribution rates against the mock server."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from pymeinverein import BadRequestError, LookupFailedError, NotFoundError
from pymeinverein.api.clubs import ClubClient
from pymeinverein.models import RateInterval, RateType

ERIKA, MAX = 7002, 7003


async def test_rates(club: ClubClient) -> None:
    rates = await club.contributions.rates()
    assert [(r.name, r.amount, r.interval) for r in rates] == [
        ("Mitgliedsbeitrag", "120.00", RateInterval.YEARLY)
    ]
    assert (await club.contributions.get("Mitgliedsbeitrag")).id == rates[0].id
    with pytest.raises(LookupFailedError, match="'Mitgliedsbeitrag'"):
        await club.contributions.get("Jugend")


async def test_rate_lifecycle(club: ClubClient) -> None:
    youth = await club.contributions.create(
        "Jugend", Decimal("60"), interval=RateInterval.HALF_YEARLY
    )
    assert (youth.name, youth.amount, youth.interval, youth.type) == (
        "Jugend",
        "60.00",
        RateInterval.HALF_YEARLY,
        RateType.REGULAR,
    )
    updated = await club.contributions.update(youth, amount=65.5, name="Jugendliche")
    assert (updated.name, updated.amount, updated.interval) == (
        "Jugendliche",
        "65.50",
        RateInterval.HALF_YEARLY,
    )
    # Unchanged fields survive; the text amount the API sent is posted as number.
    renamed = await club.contributions.update("Jugendliche", name="U18")
    assert (renamed.name, renamed.amount) == ("U18", "65.50")

    await club.contributions.delete("U18")
    assert len(await club.contributions.rates()) == 1
    with pytest.raises(NotFoundError):
        await club.contributions.delete(youth.id)


async def test_amount_must_be_a_number_on_the_wire(club: ClubClient) -> None:
    with pytest.raises(BadRequestError, match="amount: NO_NUMBER"):
        await club._transport.post(
            f"/protected/mv365/club/{club.id}/contribution/rates",
            {"name": "Text", "amount": "12.50"},
        )


async def test_assign_and_unassign(club: ClubClient) -> None:
    youth = await club.contributions.create("Jugend", 60)
    result = await club.contributions.assign(
        [ERIKA, MAX], "Jugend", next_due=date(2027, 1, 1)
    )
    assert result.ok
    erika = await club.members.get(ERIKA)
    assert len(erika.club_member_contribution_rates) == 1
    entry = erika.club_member_contribution_rates[0]
    assert entry["nextDueDate"].startswith("2027-01-01")
    assert entry["clubMemberContributionRateItems"][0]["amount"] == "60.00"

    await club.contributions.assign(
        [ERIKA], "Mitgliedsbeitrag", next_due=date(2027, 6, 1)
    )
    assert len((await club.members.get(ERIKA)).club_member_contribution_rates) == 2
    await club.contributions.assign(
        [ERIKA], "Mitgliedsbeitrag", next_due=date(2028, 1, 1), overwrite=True
    )
    assert len((await club.members.get(ERIKA)).club_member_contribution_rates) == 1

    assert (await club.contributions.unassign([MAX], [youth])).ok
    assert (await club.members.get(MAX)).club_member_contribution_rates == []


async def test_deleting_a_rate_removes_it_from_members(club: ClubClient) -> None:
    youth = await club.contributions.create("Jugend", 60)
    await club.contributions.assign([MAX], youth, next_due=date(2027, 1, 1))
    await club.contributions.delete(youth)
    assert (await club.members.get(MAX)).club_member_contribution_rates == []
