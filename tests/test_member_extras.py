"""Custom field values, pictures, membership periods and bulk edits (mock)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from pymeinverein import LookupFailedError, MemberState, NotFoundError
from pymeinverein.api.bulk import custom_values
from pymeinverein.api.clubs import ClubClient
from pymeinverein.models import CommunicationChannel, PaymentMethod
from pymeinverein.testing import DEMO_CLUB_ID, MockServer, seed

ERIKA, MAX, LENA, JONAS = 7002, 7003, 7004, 7005


# ---------------------------------------------------------------- custom fields


async def test_set_and_clear_custom_field(club: ClubClient) -> None:
    await club.members.set_custom_field(JONAS, "Position", "Mittelfeld")
    await club.members.set_custom_field(JONAS, seed.FIELD_ELIGIBLE, True)
    member = await club.members.get(JONAS)
    assert member.custom_values == {
        seed.FIELD_POSITION: ["Mittelfeld"],
        seed.FIELD_ELIGIBLE: ["true"],
    }

    await club.members.set_custom_field(JONAS, "Position", "Tor")  # overwrite
    await club.members.clear_custom_field(JONAS, "Spielberechtigt")
    assert (await club.members.get(JONAS)).custom_values == {
        seed.FIELD_POSITION: ["Tor"]
    }
    # The new value shows up in list rows and exports as well.
    text = await club.members.export(
        format="csv", search="Jonas", fields=["lastName", "custom.Position"]
    )
    assert text.splitlines()[1] == "Test,Tor"


async def test_custom_field_lookup_errors(club: ClubClient) -> None:
    with pytest.raises(LookupFailedError, match="'Position'"):
        await club.members.set_custom_field(JONAS, "Schuhgröße", 44)
    with pytest.raises(NotFoundError):
        await club.members.set_custom_field(1, "Position", "Tor")


def test_custom_values_conversion() -> None:
    assert custom_values("Tor") == ["Tor"]
    assert custom_values(True) == ["true"] and custom_values(False) == ["false"]
    assert custom_values(42) == ["42"]
    assert custom_values(date(2026, 1, 31)) == ["2026-01-31"]
    assert custom_values(["a", "b"]) == ["a", "b"]
    assert custom_values(None) == []


# --------------------------------------------------------------------- pictures


async def test_picture_upload_and_delete(
    server: MockServer, club: ClubClient, tmp_path: Path
) -> None:
    image = b"\xff\xd8\xff\xe0fake-jpeg\xff\xd9"
    await club.members.set_picture(MAX, image)
    assert await club.members.picture(MAX) == image
    assert (await club.members.get(MAX)).picture_exists is True

    file = tmp_path / "other.png"
    file.write_bytes(b"\x89PNG-fake")
    await club.members.set_picture(MAX, file, content_type="image/png")
    assert server.state.pictures[MAX] == b"\x89PNG-fake"

    await club.members.delete_picture(MAX)
    assert (await club.members.get(MAX)).picture_exists is False
    with pytest.raises(NotFoundError):
        await club.members.picture(MAX)


# ------------------------------------------------------------------- membership


async def test_status_cannot_be_set_directly(club: ClubClient) -> None:
    updated = await club.members.update(ERIKA, state=1, membership_end_at="2024-12-31")
    assert updated.state == MemberState.ACTIVE
    assert updated.membership_end_at is None


async def test_set_membership_adds_and_changes_periods(club: ClubClient) -> None:
    created = await club.members.create(
        last_name="Neu", membership_begin_at=date(2024, 1, 1)
    )
    assert created.histories == []  # nothing is added automatically

    joined = await club.members.set_membership(
        created.id, "1. Mannschaft - Damen/Spieler", start=date(2024, 2, 1)
    )
    assert [(h.sub_area_id, h.status) for h in joined.histories] == [
        (seed.PLAYERS_WOMEN, MemberState.ACTIVE)
    ]
    row = (await club.members.list(search="Neu"))[0]
    assert row.departments == ["1. Mannschaft - Damen"]

    passive = await club.members.set_membership(
        created.id, seed.PLAYERS_WOMEN, status=MemberState.PASSIVE, honoured=True
    )
    assert passive.state == MemberState.PASSIVE and passive.is_honoured is True
    assert len(passive.histories) == 1  # changed, not duplicated
    assert passive.histories[0].membership_start is not None
    assert passive.histories[0].membership_start.date() == date(2024, 2, 1)

    both = await club.members.set_membership(created.id, "1. Mannschaft - Herren")
    assert both.state == MemberState.ACTIVE
    assert {h.sub_area_id for h in both.histories} == {
        seed.PLAYERS_WOMEN,
        seed.DEPARTMENT_MEN,
    }


async def test_end_membership(club: ClubClient) -> None:
    former = await club.members.end_membership(ERIKA, date(2025, 6, 30))
    assert former.state == MemberState.FORMER
    assert former.membership_end_at is not None
    assert former.membership_end_at.date() == date(2025, 6, 30)
    assert all(h.is_former for h in former.histories)
    former_list = await club.members.list(from_list="Ehemalige Mitglieder")
    assert ERIKA in [m.id for m in former_list]
    assert (await club.members.list(search="Erika"))[0].departments == []


async def test_end_membership_without_periods(club: ClubClient) -> None:
    created = await club.members.create(
        last_name="Kurz", membership_begin_at=date(2024, 1, 1)
    )
    former = await club.members.end_membership(created.id, date(2024, 3, 31))
    assert former.state == MemberState.FORMER
    assert [(h.sub_area_id, h.is_former) for h in former.histories] == [(None, True)]
    assert former.histories[0].membership_start is not None
    assert former.histories[0].membership_start.date() == date(2024, 1, 1)


async def test_resolve_sub_area(club: ClubClient) -> None:
    resolve = club.master_data.resolve_sub_area
    assert await resolve(seed.PLAYERS_MEN) == seed.PLAYERS_MEN
    assert await resolve("1. Mannschaft - Herren") == seed.DEPARTMENT_MEN
    assert await resolve("1. Mannschaft - Herren/Spieler") == seed.PLAYERS_MEN
    with pytest.raises(LookupFailedError, match="found 2"):
        await resolve("Spieler")  # exists in both teams
    with pytest.raises(LookupFailedError, match="found 0"):
        await resolve("1. Mannschaft - Herren/Trainer")


# ------------------------------------------------------------------------- bulk


async def test_bulk_custom_fields_and_notes(
    server: MockServer, club: ClubClient
) -> None:
    result = await club.members.bulk.set_custom_fields(
        [LENA, JONAS], {"Position": "Sturm", seed.FIELD_ELIGIBLE: False}, notes="U23"
    )
    assert result.ok
    for member_id in (LENA, JONAS):
        member = await club.members.get(member_id)
        assert member.custom_values == {
            seed.FIELD_POSITION: ["Sturm"],
            seed.FIELD_ELIGIBLE: ["false"],
        }
        assert member.notes == "U23"
    assert server.state.members[DEMO_CLUB_ID][ERIKA]["notes"] is None


async def test_bulk_communication_channel(club: ClubClient) -> None:
    result = await club.members.bulk.set_communication_channel(
        [ERIKA, MAX], CommunicationChannel.LETTER
    )
    assert result.ok
    assert (await club.members.get(MAX)).communication_channel == 1


async def test_bulk_payment_method_reports_skips(club: ClubClient) -> None:
    result = await club.members.bulk.set_payment_method(
        [ERIKA, MAX], PaymentMethod.SEPA_DEBIT
    )
    assert not result.ok
    assert result.skipped_club_member_ids == [ERIKA, MAX]
    assert {skip.reason for skip in result.skips} == {"NO_SEPA_MANDATE"}
    assert (
        await club.members.bulk.set_payment_method([ERIKA], PaymentMethod.INVOICE)
    ).ok


async def test_bulk_memberships(club: ClubClient) -> None:
    added = await club.members.bulk.add_membership(
        [LENA, JONAS], "1. Mannschaft - Herren", start=date(2025, 1, 1)
    )
    assert added.ok
    lena = (await club.members.list(search="Lena"))[0]
    assert lena.departments == ["1. Mannschaft - Damen", "1. Mannschaft - Herren"]

    ended = await club.members.bulk.update_membership(
        [LENA, ERIKA],
        seed.DEPARTMENT_MEN,
        end=date(2025, 12, 31),
        status=MemberState.FORMER,
    )
    # Erika has no membership in that department.
    assert [(s.club_member_id, s.reason) for s in ended.skips] == [
        (ERIKA, "NOT_A_CLUB_MEMBER")
    ]
    lena = (await club.members.list(search="Lena"))[0]
    assert lena.departments == ["1. Mannschaft - Damen"]
    assert lena.state == MemberState.ACTIVE
