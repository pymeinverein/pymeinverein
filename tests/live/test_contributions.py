"""Live test for contribution rates. Nothing is billed."""

from __future__ import annotations

from datetime import date

import pytest

from pymeinverein.api.clubs import ClubClient
from pymeinverein.models import RateInterval

from .conftest import MARKER

pytestmark = pytest.mark.live


async def test_rate_lifecycle(demo_club: ClubClient) -> None:
    club = demo_club
    before = [rate.id for rate in await club.contributions.rates()]
    try:
        rate = await club.contributions.create(
            f"{MARKER} rate", 12.5, interval=RateInterval.YEARLY
        )
        assert (rate.amount, rate.interval) == ("12.50", RateInterval.YEARLY)

        updated = await club.contributions.update(
            rate, name=f"{MARKER} rate2", amount=15
        )
        assert (updated.name, updated.amount) == (f"{MARKER} rate2", "15.00")
        assert (await club.contributions.get(rate.id)).amount == "15.00"

        member = await club.members.create(first_name=MARKER, last_name="Payer")
        assigned = await club.contributions.assign(
            [member.id], rate.id, next_due=date(2030, 1, 1)
        )
        assert assigned.ok
        entries = (await club.members.get(member.id)).club_member_contribution_rates
        assert len(entries) == 1
        assert entries[0]["nextDueDate"].startswith("2030-01-01")
        item = entries[0]["clubMemberContributionRateItems"][0]
        assert (item["clubContributionRateId"], item["amount"]) == (rate.id, "15.00")

        assert (await club.contributions.unassign([member.id], [rate.id])).ok
        assert (await club.members.get(member.id)).club_member_contribution_rates == []

        await club.contributions.delete(rate.id)
    finally:
        for leftover in await club.contributions.rates():
            if MARKER in leftover.name:
                await club.contributions.delete(leftover.id)
    assert [rate.id for rate in await club.contributions.rates()] == before
