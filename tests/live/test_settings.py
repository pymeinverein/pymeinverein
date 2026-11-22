"""Live test for club settings. Changes are undone; the logo is restored."""

from __future__ import annotations

import pytest

from pymeinverein.api.clubs import ClubClient

pytestmark = pytest.mark.live


async def test_read_settings(demo_club: ClubClient) -> None:
    club = demo_club
    details = await club.settings.details()
    assert details.id == club.id and details.is_demo
    assert await club.settings.categories()
    assert any(s.label == "Frau" for s in await club.settings.salutations())
    numbering = await club.settings.numbering()
    assert numbering.length
    assert (await club.settings.next_number()).isdecimal()


async def test_logo_roundtrip(demo_club: ClubClient) -> None:
    club = demo_club
    original = await club.settings.logo("large")
    if not original:
        pytest.skip("the demo club has no logo to restore afterwards")
    try:
        await club.settings.delete_logo()
        assert await club.settings.logo() == b""
    finally:
        await club.settings.set_logo(original)
    assert await club.settings.logo("large")


async def test_title_favourite_roundtrip(demo_club: ClubClient) -> None:
    club = demo_club
    title = (await club.settings.titles())[0]
    flipped = not title.is_favorite
    try:
        changed = await club.settings.update_title(title.id, favorite=flipped)
        assert changed.is_favorite is flipped and changed.label == title.label
    finally:
        await club.settings.update_title(title.id, favorite=bool(title.is_favorite))
