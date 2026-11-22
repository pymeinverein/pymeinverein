"""Club settings against the mock server."""

from __future__ import annotations

from pathlib import Path

import pytest

from pymeinverein import BadRequestError, LookupFailedError, MeinVereinClient
from pymeinverein.api.clubs import ClubClient
from pymeinverein.testing import REGULAR_CLUB_ID


async def test_details(club: ClubClient) -> None:
    details = await club.settings.details()
    assert (details.id, details.name, details.is_demo) == (club.id, "Demoverein", True)


async def test_update_needs_a_category(
    client: MeinVereinClient, club: ClubClient
) -> None:
    # The demo club has no category, which the API insists on.
    with pytest.raises(BadRequestError, match="categoryId"):
        await club.settings.update(phone="030 1")
    fixed = await club.settings.update(phone="030 1", category_id=15)
    assert (fixed.phone, fixed.category_id) == ("030 1", 15)

    regular = await client.clubs.get(REGULAR_CLUB_ID)
    updated = await regular.settings.update(name2="seit 1900", website="example.org")
    assert (updated.name, updated.name2, updated.website) == (
        "Musterverein e.V.",
        "seit 1900",
        "example.org",
    )
    assert (await regular.settings.details()).name2 == "seit 1900"


async def test_categories(club: ClubClient) -> None:
    categories = await club.settings.categories()
    assert categories[0].name == "Sportverein"
    assert [c.name for c in categories[0].children or []] == ["Fußball", "Golf"]


async def test_logo(club: ClubClient, tmp_path: Path) -> None:
    assert await club.settings.logo() == b""  # no logo yet
    await club.settings.set_logo(b"\xff\xd8logo")
    assert await club.settings.logo("large") == b"\xff\xd8logo"
    file = tmp_path / "logo.png"
    file.write_bytes(b"png-logo")
    await club.settings.set_logo(file, content_type="image/png")
    assert await club.settings.logo() == b"png-logo"
    await club.settings.delete_logo()
    assert await club.settings.logo() == b""


async def test_salutations(club: ClubClient) -> None:
    salutations = await club.settings.salutations()
    assert [s.label for s in salutations] == ["keine Angabe", "Frau", "Herr"]
    assert salutations[2].address == "Herr"
    assert salutations[1].formal_letter_salutation is not None


async def test_titles(club: ClubClient) -> None:
    assert [t.label for t in await club.settings.titles()] == ["Dr.", "Prof."]
    created = await club.settings.create_title("Dipl.-Ing.")
    assert created.label == "Dipl.-Ing." and created.is_favorite is False

    favourite = await club.settings.update_title(created.id, favorite=True)
    assert (favourite.label, favourite.is_favorite) == ("Dipl.-Ing.", True)
    renamed = await club.settings.update_title(created.id, label="Dipl. Ing.")
    assert (renamed.label, renamed.is_favorite) == ("Dipl. Ing.", True)
    assert len((await club.master_data.get()).titles) == 3

    with pytest.raises(LookupFailedError):
        await club.settings.update_title(1, label="x")


async def test_numbering(club: ClubClient) -> None:
    numbering = await club.settings.numbering()
    assert (numbering.length, numbering.date_part_type, numbering.current_value) == (
        6,
        "YYYY",
        "33",
    )
    assert await club.settings.next_number() == "2026000033"
    with pytest.raises(BadRequestError):
        await club.settings.numbering("member")
