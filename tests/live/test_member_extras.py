"""Live tests for custom field values, pictures, membership periods, bulk edits."""

from __future__ import annotations

from datetime import date

import pytest

from pymeinverein import MembershipPeriod, MemberState
from pymeinverein.api.clubs import ClubClient
from pymeinverein.models import CommunicationChannel, PaymentMethod

from .conftest import MARKER

pytestmark = pytest.mark.live


async def test_custom_fields_and_picture(demo_club: ClubClient) -> None:
    club = demo_club
    fields = await club.master_data.individual_fields()
    if not fields:
        pytest.skip("the demo club has no custom fields")
    field = fields[0]
    member = await club.members.create(first_name=MARKER, last_name="Extras")

    await club.members.set_custom_field(member.id, field.name, "pymv")
    assert (await club.members.get(member.id)).custom_values[field.id] == ["pymv"]
    await club.members.set_custom_field(member.id, field.id, "again")  # overwrite
    assert (await club.members.get(member.id)).custom_values[field.id] == ["again"]
    await club.members.clear_custom_field(member.id, field)
    assert field.id not in (await club.members.get(member.id)).custom_values

    donor = next(m for m in await club.members.query() if m.picture_exists)
    image = await club.members.picture(donor.id)
    await club.members.set_picture(member.id, image)
    assert (await club.members.get(member.id)).picture_exists is True
    assert await club.members.picture(member.id, "small")
    await club.members.delete_picture(member.id)
    assert (await club.members.get(member.id)).picture_exists is False


async def test_membership_periods(demo_club: ClubClient) -> None:
    club = demo_club
    department = next(
        sub for area in await club.master_data.areas() for sub in area.sub_areas
    )
    member = await club.members.create(
        first_name=MARKER, last_name="Periods", membership_begin_at=date(2020, 1, 1)
    )
    assert member.histories == []

    ignored = await club.members.update(member.id, state=1)
    assert ignored.state == MemberState.ACTIVE  # the status is derived

    joined = await club.members.set_membership(
        member.id, department.id, start=date(2021, 1, 1)
    )
    assert [h.sub_area_id for h in joined.histories] == [department.id]
    row = (await club.members.list(search=MARKER))[0]
    assert department.name in [area.name for area in row.club_sub_areas]

    passive = await club.members.set_membership(
        member.id, department.id, status=MemberState.PASSIVE
    )
    assert passive.state == MemberState.PASSIVE and len(passive.histories) == 1

    former = await club.members.end_membership(member.id, date(2024, 12, 31))
    assert former.state == MemberState.FORMER
    assert former.membership_end_at is not None
    assert former.membership_end_at.date() == date(2024, 12, 31)


async def test_set_memberships(demo_club: ClubClient) -> None:
    club = demo_club
    first, second = [
        sub for area in await club.master_data.areas() for sub in area.sub_areas
    ][:2]
    member = await club.members.create(first_name=MARKER, last_name="Memberships")
    chained = await club.members.set_memberships(
        member.id,
        [
            MembershipPeriod(first.id, date(2009, 1, 1), date(2009, 12, 31)),
            MembershipPeriod(second.id, date(2010, 1, 1)),
        ],
    )
    periods = {h.sub_area_id: h for h in chained.histories}
    assert periods[first.id].status == MemberState.FORMER
    assert periods[second.id].membership_end is None
    assert chained.state == MemberState.ACTIVE

    reopened = await club.members.set_memberships(
        member.id, [MembershipPeriod(first.id, date(2009, 1, 1))]
    )
    again = {h.sub_area_id: h for h in reopened.histories}
    assert again[first.id].membership_end is None  # the end date was removed
    assert again[first.id].status == MemberState.ACTIVE
    assert second.id in again


async def test_bulk_edits(demo_club: ClubClient) -> None:
    club = demo_club
    first = await club.members.create(first_name=MARKER, last_name="BulkA")
    second = await club.members.create(first_name=MARKER, last_name="BulkB")
    ids = [first.id, second.id]

    channel = await club.members.bulk.set_communication_channel(
        ids, CommunicationChannel.LETTER
    )
    assert channel.ok
    assert (await club.members.get(first.id)).communication_channel == 1

    debit = await club.members.bulk.set_payment_method(ids, PaymentMethod.SEPA_DEBIT)
    assert {skip.reason for skip in debit.skips} == {"NO_SEPA_MANDATE"}

    fields = await club.master_data.individual_fields()
    if fields:
        done = await club.members.bulk.set_custom_fields(
            ids, {fields[0].id: "bulk"}, notes="bulk note"
        )
        assert done.ok
        second_now = await club.members.get(second.id)
        assert second_now.custom_values[fields[0].id] == ["bulk"]
        assert second_now.notes == "bulk note"

    department = next(
        sub for area in await club.master_data.areas() for sub in area.sub_areas
    )
    added = await club.members.bulk.add_membership(
        ids, department.id, start=date(2022, 1, 1)
    )
    assert added.ok
    changed = await club.members.bulk.update_membership(
        ids, department.id, end=date(2024, 12, 31), status=MemberState.FORMER
    )
    assert changed.ok
    periods = (await club.members.get(first.id)).histories
    assert [(h.sub_area_id, h.is_former) for h in periods] == [(department.id, True)]
