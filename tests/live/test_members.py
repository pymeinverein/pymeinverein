"""Live tests for members, lists and master data (see tests/live/conftest.py)."""

from __future__ import annotations

import json
from datetime import date

import pytest

from pymeinverein import MemberType, NotFoundError
from pymeinverein.api.clubs import ClubClient

from .conftest import MARKER

pytestmark = pytest.mark.live


async def test_member_lifecycle(demo_club: ClubClient) -> None:
    club = demo_club
    count_before = len(await club.members.list())

    created = await club.members.create(
        first_name=MARKER,
        last_name="Lifecycle",
        email="pymeinverein-test@example.org",
        birthday=date(1990, 5, 17),
        membership_begin_at=date(2020, 3, 1),
        address={
            "address_line1": "Teststr. 1",
            "zip": "12345",
            "city": "Teststadt",
            "country_id": 2,  # Germany; the API does not default the country
        },
    )
    assert created.full_name == f"{MARKER} Lifecycle"
    assert created.type == MemberType.MEMBER
    assert created.birthday is not None and created.birthday.date() == date(1990, 5, 17)
    assert created.address is not None and created.address.city == "Teststadt"

    updated = await club.members.update(
        created.id, phone="0123 456", address={"city": "Anderstadt"}
    )
    assert updated.phone == "0123 456"

    fetched = await club.members.get(created.id)
    assert fetched.phone == "0123 456"
    assert fetched.email == "pymeinverein-test@example.org"  # not cleared
    assert fetched.address is not None
    assert fetched.address.city == "Anderstadt"
    assert fetched.address.address_line1 == "Teststr. 1"
    assert fetched.birthday is not None and fetched.birthday.date() == date(1990, 5, 17)

    found = await club.members.list(search=MARKER)
    assert [m.id for m in found] == [created.id]
    assert len(await club.members.list()) == count_before + 1

    exported = json.loads(await club.members.export(search=MARKER))
    assert exported == [
        {
            "memberId": created.member_id,
            "firstName": MARKER,
            "lastName": "Lifecycle",
            "email": "pymeinverein-test@example.org",
        }
    ]
    csv_text = await club.members.export(format="csv", search=MARKER, fields="contact")
    assert csv_text.splitlines()[1].endswith("Teststr. 1,12345,Anderstadt,Deutschland")

    result = await club.members.delete(created.id)
    assert result.deleted_count == 1
    with pytest.raises(NotFoundError):
        await club.members.get(created.id)
    assert len(await club.members.list()) == count_before


async def test_list_lifecycle(demo_club: ClubClient) -> None:
    club = demo_club
    someone = (await club.members.list(type="member", status="active"))[0]

    created = await club.lists.create(f"{MARKER} list")
    await club.lists.add_members(created, [someone.id])
    assert [m.id for m in await club.lists.members(created)] == [someone.id]

    removed = await club.lists.remove_members(created, [someone.id])
    assert removed.removed_count == 1
    await club.lists.rename(created, f"{MARKER} renamed")
    assert (await club.lists.get(created.id)).name == f"{MARKER} renamed"

    await club.lists.delete(created)
    assert all(item.id != created.id for item in await club.lists.all())


async def test_read_only_lookups(demo_club: ClubClient) -> None:
    club = demo_club
    master = await club.master_data.get()
    assert master.form_of_addresses and master.club_areas
    assert any(c.iso3166_code == "DE" for c in await club.master_data.countries())
    assert await club.master_data.roles()
    assert (await club.members.next_number()).isdecimal()
    assert len(await club.members.query([("type", "=", 2)])) >= 1
