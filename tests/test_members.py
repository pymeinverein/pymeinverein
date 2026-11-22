"""Reading, creating, changing and deleting members against the mock server."""

from __future__ import annotations

from datetime import date

import pytest

from pymeinverein import (
    Address,
    BadRequestError,
    Gender,
    MeinVereinClient,
    MemberFilter,
    MemberState,
    MemberType,
    NotFoundError,
)
from pymeinverein.api.clubs import ClubClient
from pymeinverein.models import ListCriterion, Member
from pymeinverein.testing import DEMO_CLUB_ID, DEMO_EMAIL, REGULAR_CLUB_ID, MockServer
from pymeinverein.testing import seed

ERIKA = 7002


def names(members: list[Member]) -> list[str | None]:
    return [member.last_name for member in members]


# ----------------------------------------------------------------------- reading


async def test_get_member(club: ClubClient) -> None:
    member = await club.members.get(ERIKA)
    assert member.full_name == "Erika Beispiel"
    assert member.member_id == "2"
    assert member.type == MemberType.MEMBER and member.is_member
    assert member.state == MemberState.ACTIVE and member.is_active
    assert member.gender == Gender.FEMALE
    assert member.birthday is not None and member.birthday.date() == date(1988, 4, 12)
    assert member.address is not None
    assert member.address.zip == "10115"
    assert member.address.country == "Deutschland"
    assert member.histories[0].sub_area_id == seed.PLAYERS_WOMEN
    assert member.custom_values == {
        seed.FIELD_ELIGIBLE: ["true"],
        seed.FIELD_POSITION: ["Tor"],
    }


async def test_get_unknown_member(club: ClubClient) -> None:
    with pytest.raises(NotFoundError):
        await club.members.get(1)


async def test_members_are_scoped_to_their_club(client: MeinVereinClient) -> None:
    other = await client.clubs.get(REGULAR_CLUB_ID)
    assert [m.full_name for m in await other.members.list()] == [
        "Demo User",
        "Clara Echt",
    ]
    with pytest.raises(NotFoundError):
        await other.members.get(ERIKA)


async def test_list_everyone(club: ClubClient) -> None:
    members = await club.members.list()
    assert len(members) == 10
    erika = next(m for m in members if m.id == ERIKA)
    # List rows carry resolved departments, roles and custom values.
    assert erika.departments == ["1. Mannschaft - Damen"]
    assert [area.name for area in erika.club_sub_areas] == [
        "Spieler",
        "1. Mannschaft - Damen",
    ]
    assert [role.name for role in erika.roles] == ["Finanzverwalter"]
    assert erika.custom_values[seed.FIELD_POSITION] == ["Tor"]


async def test_list_filters(club: ClubClient) -> None:
    active = await club.members.list(type="member", status="active")
    assert names(active) == ["User", "Beispiel", "Muster", "Probe", "Test"]

    former = await club.members.list(status=MemberState.FORMER)
    assert names(former) == ["Vorlage", "Entwurf"]

    contacts = await club.members.list(type=MemberType.CONTACT)
    assert names(contacts) == ["Kontakt", "Sporthaus Beispiel GmbH"]
    assert all(m.is_contact for m in contacts)

    women = await club.members.list(department="1. Mannschaft - Damen")
    assert names(women) == ["Beispiel", "Probe"]
    assert names(await club.members.list(department=seed.DEPARTMENT_MEN)) == [
        "Muster",
        "Test",
    ]

    assert names(await club.members.list(role="Administrator")) == ["User"]
    assert names(await club.members.list(role=seed.ROLE_MEMBER)) == ["Muster"]
    assert names(await club.members.list(search="ERIKA")) == ["Beispiel"]
    assert names(await club.members.list(search="@sporthaus")) == [
        "Sporthaus Beispiel GmbH"
    ]

    no_email = await club.members.list(type="member", where=lambda m: not m.email)
    assert names(no_email) == ["Test"]


async def test_list_from_named_list(club: ClubClient) -> None:
    board = await club.members.list(from_list="Vorstand")
    assert [m.full_name for m in board] == ["Demo User", "Erika Beispiel"]
    former = await club.members.list(from_list="Ehemalige Mitglieder", search="greta")
    assert [m.full_name for m in former] == ["Greta Vorlage"]


def test_filter_rejects_unknown_names() -> None:
    with pytest.raises(ValueError, match="active, former, passive"):
        MemberFilter(status="retired")


async def test_query_with_server_side_criteria(club: ClubClient) -> None:
    assert len(await club.members.query()) == 10
    former = await club.members.query([("type", "=", 1), ("state", "=", 1)])
    assert [m.last_name for m in former] == ["Vorlage", "Entwurf"]
    by_model = await club.members.query(
        [ListCriterion(column_name="lastName", value="Muster")]
    )
    assert [m.id for m in by_model] == [7003]


async def test_next_number_and_user_exists(club: ClubClient) -> None:
    assert await club.members.next_number() == "11"
    assert await club.members.user_exists(DEMO_EMAIL) is True
    assert await club.members.user_exists("nobody@example.org") is False


async def test_picture(club: ClubClient) -> None:
    assert (await club.members.picture(ERIKA)).startswith(b"\xff\xd8")
    with pytest.raises(NotFoundError):
        await club.members.picture(7003)


# ---------------------------------------------------------------------- creating


async def test_create_minimal_member(server: MockServer, club: ClubClient) -> None:
    member = await club.members.create(last_name="Neu")
    assert member.last_name == "Neu"
    assert member.type == MemberType.MEMBER
    assert member.is_person is True
    assert member.member_id == "11"  # assigned by the server
    assert member.membership_begin_at is not None
    assert member.id in server.state.members[DEMO_CLUB_ID]


async def test_create_member_with_details(club: ClubClient) -> None:
    member = await club.members.create(
        first_name="Ada",
        last_name="Lovelace",
        email="ada@example.org",
        gender=Gender.FEMALE,
        birthday=date(1815, 12, 10),
        membership_begin_at=date(2024, 1, 1),
        mobile_phone="0171 000",
        address=Address(address_line1="Main St 1", zip="12345", city="London"),
        member_id="A-1",
    )
    assert member.full_name == "Ada Lovelace"
    assert member.email == "ada@example.org"
    assert member.gender == Gender.FEMALE
    assert member.birthday is not None and member.birthday.date() == date(1815, 12, 10)
    assert member.membership_begin_at is not None
    assert member.membership_begin_at.date() == date(2024, 1, 1)
    assert member.mobile_phone == "0171 000"
    assert member.member_id == "A-1"
    assert member.address is not None and member.address.city == "London"


async def test_create_contact_and_company(club: ClubClient) -> None:
    contact = await club.members.create(
        last_name="Kontaktperson", type=MemberType.CONTACT
    )
    assert contact.type == MemberType.CONTACT and contact.is_person is True
    assert contact.membership_begin_at is None
    company = await club.members.create(last_name="Firma AG", type=MemberType.COMPANY)
    assert company.is_person is False


async def test_create_accepts_api_field_names(club: ClubClient) -> None:
    member = await club.members.create(last_name="Camel", mobilePhone="0172 1")
    assert member.mobile_phone == "0172 1"


async def test_create_is_validated_by_the_server(club: ClubClient) -> None:
    with pytest.raises(BadRequestError) as excinfo:
        await club.members.create(last_name=None)  # type: ignore[arg-type]
    assert excinfo.value.status == 400
    assert excinfo.value.name == "BadRequestError"
    assert "lastName: Invalid value" in str(excinfo.value)


# ---------------------------------------------------------------------- changing


async def test_update_keeps_everything_else(
    server: MockServer, club: ClubClient
) -> None:
    before = dict(server.state.members[DEMO_CLUB_ID][ERIKA])
    updated = await club.members.update(ERIKA, phone="030 999", notes="called")
    assert updated.phone == "030 999" and updated.notes == "called"

    after = server.state.members[DEMO_CLUB_ID][ERIKA]
    changed = {key for key in after if after[key] != before.get(key)}
    assert changed == {"phone", "notes", "updatedAt", "editedAtDate"}
    # The mock clears the e-mail when it is missing from the body, like the real
    # API does - so this proves that the whole object was sent.
    assert after["email"] == "erika.beispiel@example.org"


async def test_update_merges_address(club: ClubClient) -> None:
    updated = await club.members.update(ERIKA, address={"city": "Potsdam"})
    assert updated.address is not None
    assert updated.address.city == "Potsdam"
    assert updated.address.address_line1 == "Musterweg 1"
    assert updated.address.zip == "10115"


async def test_update_values_are_converted(club: ClubClient) -> None:
    updated = await club.members.update(
        ERIKA,
        birthday=date(1990, 1, 2),
        gender=Gender.DIVERSE,
        marital_status=None,
        email="",
    )
    assert updated.birthday is not None and updated.birthday.date() == date(1990, 1, 2)
    assert updated.gender == Gender.DIVERSE
    assert updated.email == ""


async def test_update_unknown_member(club: ClubClient) -> None:
    with pytest.raises(NotFoundError):
        await club.members.update(1, phone="1")


# ---------------------------------------------------------------------- deleting


async def test_delete_member(server: MockServer, club: ClubClient) -> None:
    result = await club.members.delete(7003)
    assert result.deleted_count == 1 and result.skipped_count == 0
    assert 7003 not in server.state.members[DEMO_CLUB_ID]
    with pytest.raises(NotFoundError):
        await club.members.get(7003)


async def test_delete_several_members(server: MockServer, club: ClubClient) -> None:
    result = await club.members.delete(7006, 7007)
    assert result.deleted_count == 2
    assert len(server.state.members[DEMO_CLUB_ID]) == 8


async def test_delete_checks_ids_before_deleting_anything(
    server: MockServer, club: ClubClient
) -> None:
    with pytest.raises(NotFoundError):
        await club.members.delete(7003, 1)
    assert 7003 in server.state.members[DEMO_CLUB_ID]
    assert ("POST", f"/protected/club/{DEMO_CLUB_ID}/members/delete") not in (
        server.state.requests
    )


async def test_delete_missing_ok(club: ClubClient) -> None:
    # The API (and the mock) count unknown ids as deleted.
    result = await club.members.delete(1, missing_ok=True)
    assert result.deleted_count == 1


async def test_delete_nothing(server: MockServer, club: ClubClient) -> None:
    server.state.requests.clear()
    assert (await club.members.delete()).deleted_count == 0
    assert server.state.requests == []


# ------------------------------------------------------- details of the protocol


async def test_calls_use_the_same_api_versions_as_the_web_application(
    server: MockServer, club: ClubClient
) -> None:
    server.state.requests.clear()
    server.state.api_versions.clear()
    await club.members.update(ERIKA, notes="x")
    await club.lists.members(seed.LIST_BOARD)
    calls = dict(zip(server.state.requests, server.state.api_versions))
    legacy = f"/protected/mv365/clubs/{DEMO_CLUB_ID}/members/{ERIKA}"
    assert calls[("GET", legacy)] == "v2"
    assert calls[("PATCH", legacy)] == "v2"
    assert calls[
        ("POST", f"/protected/club/{DEMO_CLUB_ID}/list/{seed.LIST_BOARD}")
    ] == ("v3")


async def test_create_uses_the_endpoint_that_stores_all_fields(
    server: MockServer, club: ClubClient
) -> None:
    server.state.requests.clear()
    await club.members.create(last_name="Voll", notes="kept")
    assert server.state.requests[0] == (
        "POST",
        f"/protected/mv365/clubs/{DEMO_CLUB_ID}/members",
    )
    # The quick-create endpoint of the web application drops most fields.
    transport = club._transport
    quick = await transport.post(
        f"/protected/club/{DEMO_CLUB_ID}/members",
        {"lastName": "Schnell", "notes": "lost", "phone": "1"},
    )
    stored = server.state.members[DEMO_CLUB_ID][quick["data"]["id"]]
    assert stored["notes"] is None and stored["phone"] == "1"


def test_departments_are_listed_once() -> None:
    # A member with two functions in one department: the API repeats the
    # department for each function.
    member = Member.model_validate(
        {
            "id": 1,
            "clubSubAreas": [
                {"id": 11, "name": "Spieler", "level": 2, "parentId": 10},
                {"id": 10, "name": "Damen", "level": 1},
                {"id": 12, "name": "Schiedsrichter", "level": 2, "parentId": 10},
                {"id": 10, "name": "Damen", "level": 1},
                {"id": 20, "name": "Herren", "level": 1},
            ],
        }
    )
    assert member.departments == ["Damen", "Herren"]
