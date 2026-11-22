"""Member lists and master data against the mock server."""

from __future__ import annotations

import pytest

from pymeinverein import DefaultListType, ListType, LookupFailedError, NotFoundError
from pymeinverein.api.clubs import ClubClient
from pymeinverein.models import IndividualFieldType
from pymeinverein.testing import DEMO_CLUB_ID, MockServer, seed


async def test_all_lists(club: ClubClient) -> None:
    lists = await club.lists.all()
    assert len(lists) == 10
    everyone = next(item for item in lists if item.name == "Alle Kontakte")
    assert everyone.is_default_list
    assert everyone.default_list_type == DefaultListType.ALL_CONTACTS
    assert everyone.list_type == ListType.DYNAMIC


async def test_get_list_by_id_name_and_default_type(club: ClubClient) -> None:
    assert (await club.lists.get(seed.LIST_BOARD)).name == "Vorstand"
    assert (await club.lists.get("Vorstand")).id == seed.LIST_BOARD
    former = await club.lists.get(DefaultListType.FORMER_MEMBERS)
    assert former.id == seed.LIST_FORMER
    # Department lists end with a space on the real service; names are trimmed.
    women = await club.lists.get("Abteilung 1. Mannschaft - Damen")
    assert women.department_id == seed.DEPARTMENT_WOMEN


async def test_get_list_failures(club: ClubClient) -> None:
    with pytest.raises(LookupFailedError, match="Vorstand"):
        await club.lists.get("no such list")
    # Two department lists share this default type.
    with pytest.raises(LookupFailedError, match="found 2"):
        await club.lists.get(DefaultListType.DEPARTMENT)


async def test_list_members(club: ClubClient) -> None:
    active = await club.lists.members(DefaultListType.ACTIVE_MEMBERS)
    assert [m.last_name for m in active] == [
        "User",
        "Beispiel",
        "Muster",
        "Probe",
        "Test",
    ]
    men = await club.lists.members(seed.LIST_MEN)
    assert [m.last_name for m in men] == ["Muster", "Test"]
    board = await club.lists.members("Vorstand")
    assert [m.last_name for m in board] == ["User", "Beispiel"]
    with pytest.raises(NotFoundError):
        await club.lists.members(1)


async def test_criteria(club: ClubClient) -> None:
    criteria = await club.lists.criteria(DefaultListType.FORMER_MEMBERS)
    assert [(c.column_name, c.operator, c.value) for c in criteria] == [
        ("type", "=", "1"),
        ("state", "=", "1"),
    ]


async def test_list_lifecycle(server: MockServer, club: ClubClient) -> None:
    created = await club.lists.create("Helfer")
    assert created.name == "Helfer" and created.list_type == ListType.STATIC
    assert not created.is_default_list
    assert await club.lists.members(created) == []

    await club.lists.add_members(created, [7003, 7004])
    assert [m.id for m in await club.lists.members("Helfer")] == [7003, 7004]

    result = await club.lists.remove_members(created, [7003, 9999])
    assert (result.removed_count, result.skipped_count) == (1, 1)
    assert [m.id for m in await club.lists.members(created.id)] == [7004]

    await club.lists.rename(created, "Helferteam")
    assert (await club.lists.get(created.id)).name == "Helferteam"

    await club.lists.delete("Helferteam")
    assert created.id not in server.state.lists[DEMO_CLUB_ID]
    # Deleting a list does not delete its members.
    assert 7004 in server.state.members[DEMO_CLUB_ID]


async def test_deleted_members_leave_static_lists(club: ClubClient) -> None:
    await club.members.delete(7002)
    assert [m.id for m in await club.lists.members("Vorstand")] == [7001]


async def test_master_data(club: ClubClient) -> None:
    master = await club.master_data.get()
    assert [f.label for f in master.form_of_addresses] == [
        "keine Angabe",
        "Frau",
        "Herr",
    ]
    assert [t.label for t in master.titles] == ["Dr.", "Prof."]
    assert [a.name for a in master.club_areas] == ["Mannschaften", "Rollen", "Ebene 3"]
    assert len(master.sub_areas) == 4
    assert master.club_contribution_rates[0].amount == "120.00"
    assert [f.name for f in master.individual_fields] == ["Spielberechtigt", "Position"]


async def test_master_data_lookups(club: ClubClient) -> None:
    areas = await club.master_data.areas()
    assert [s.name for s in areas[0].sub_areas] == [
        "1. Mannschaft - Damen",
        "1. Mannschaft - Herren",
    ]
    fields = await club.master_data.individual_fields()
    assert fields[0].type == IndividualFieldType.BOOLEAN
    assert fields[1].options == ["Tor", "Abwehr", "Mittelfeld", "Sturm"]

    roles = await club.master_data.roles()
    assert [r.name for r in roles] == [
        "Administrator",
        "Finanzverwalter",
        "Verwalter",
        "Mitglied",
    ]
    assert [r.member_count for r in roles] == [1, 1, 0, 1]

    countries = await club.master_data.countries()
    germany = next(c for c in countries if c.id == 2)
    assert (germany.name, germany.iso3166_code) == ("Deutschland", "DE")
